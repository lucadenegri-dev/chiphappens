# app.py
import os
from datetime import datetime

from flask import (
    Flask,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from flask_wtf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash

from config import Config
from models import db, Player, Game, Result
from forms import PlayerForm, GameCreateForm, LoginForm
from auth import AdminUser
from scoring import compute_points_table


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    # Ensure instance folder exists
    os.makedirs(app.instance_path, exist_ok=True)

    # DB init
    db.init_app(app)
    CSRFProtect(app)

    # Login manager
    login_manager = LoginManager(app)
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):
        # Single admin user pattern: id is always "admin"
        if user_id == "admin":
            return AdminUser()
        return None

    # Reverse proxy safety for hosting (Render/Railway/Heroku)
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1,
    )

    # CLI command to init DB
    @app.cli.command("init-db")
    def init_db_cmd():
        with app.app_context():
            db.create_all()
            print("Database initialized.")

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.route("/")
    def index():
        # Leaderboard + recent games
        players = Player.query.order_by(Player.name.asc()).all()
        games = Game.query.order_by(Game.date.desc()).limit(10).all()

        standings = []
        for p in players:
            points = (
                db.session.query(
                    db.func.coalesce(db.func.sum(Result.points), 0)
                )
                .filter(Result.player_id == p.id)
                .scalar()
                or 0
            )
            cash = (
                db.session.query(
                    db.func.coalesce(db.func.sum(Result.cash_delta), 0.0)
                )
                .filter(Result.player_id == p.id)
                .scalar()
                or 0.0
            )
            games_played = (
                Result.query.filter_by(player_id=p.id)
                .distinct(Result.game_id)
                .count()
            )
            standings.append(
                {
                    "player": p,
                    "points": int(points),
                    "cash": float(cash),
                    "games": games_played,
                }
            )

        standings.sort(key=lambda x: (x["points"], x["cash"]), reverse=True)
        return render_template("index.html", standings=standings, games=games)

    # --- Players -------------------------------------------------------

    @app.route("/players")
    def players():
        players = Player.query.order_by(Player.name.asc()).all()
        form = PlayerForm() if current_user.is_authenticated else None
        return render_template("players.html", players=players, form=form)

    @app.route("/players/new", methods=["GET", "POST"])
    @login_required
    def player_new():
        form = PlayerForm()
        if form.validate_on_submit():
            p = Player(name=form.name.data.strip())
            db.session.add(p)
            db.session.commit()
            flash("Giocatore creato.", "success")
            return redirect(url_for("players"))
        return render_template("player_new.html", form=form)

    @app.route("/players/<int:player_id>/delete", methods=["POST"])
    @login_required
    def player_delete(player_id):
        p = Player.query.get_or_404(player_id)
        has_results = Result.query.filter_by(player_id=p.id).first() is not None
        if has_results:
            flash(
                "Impossibile eliminare: il giocatore ha risultati associati.",
                "warning",
            )
            return redirect(url_for("players"))
        db.session.delete(p)
        db.session.commit()
        flash("Giocatore eliminato.", "success")
        return redirect(url_for("players"))

    # --- Games ---------------------------------------------------------

    @app.route("/games")
    def games():
        games = Game.query.order_by(Game.date.desc()).all()
        return render_template("games.html", games=games)

    @app.route("/games/new", methods=["GET", "POST"])
    @login_required
    def game_new():
        form = GameCreateForm()
        form.participants.choices = [
            (p.id, p.name)
            for p in Player.query.order_by(Player.name.asc()).all()
        ]

        if form.validate_on_submit():
            # 1) Lettura input base
            buy_in = float(form.buy_in.data)
            if form.date.data:
                date = form.date.data
            else:
                date = datetime.utcnow().date()
                flash(
                    "Data non inserita: impostata automaticamente alla data odierna.",
                    "warning",
                )

            # Partecipanti selezionati (lista di int)
            selected = [int(p) for p in (form.participants.data or [])]

            # 1a) Rebuy per giocatore
            rebuy_map = {}
            for k, v in request.form.items():
                if k.startswith("rebuy_"):
                    try:
                        pid = int(k.split("_", 1)[1])
                        if v in (None, ""):
                            rebuy_map[pid] = 0
                        else:
                            rebuy_map[pid] = max(int(v), 0)
                    except Exception:
                        # input sporchi vengono ignorati
                        pass

            # 1b) Vincite manuali per giocatore (campo prize_<id> nella lista drag)
            prize_map = {}
            for k, v in request.form.items():
                if k.startswith("prize_"):
                    try:
                        pid = int(k.split("_", 1)[1])
                        if v in (None, ""):
                            amount = 0.0
                        else:
                            amount = float(str(v).replace(",", "."))
                            if amount < 0:
                                amount = 0.0
                        prize_map[pid] = amount
                    except Exception:
                        # se qualcosa non torna, trattiamo come 0 e andiamo avanti
                        pass

            # 1c) Punti manuali opzionali (campo points_<id> nella lista drag)
            manual_points_map = {}
            for k, v in request.form.items():
                if k.startswith("points_"):
                    try:
                        pid = int(k.split("_", 1)[1])
                        if v in (None, ""):
                            # se vuoto, lascia ai punti automatici
                            continue
                        pts = int(v)
                        if pts < 0:
                            pts = 0
                        manual_points_map[pid] = pts
                    except Exception:
                        # input non valido -> ignora e usa i punti automatici
                        pass

            # 2) Validazioni hard-stop
            if buy_in <= 0:
                flash("Il buy-in deve essere maggiore di 0.", "danger")
                return render_template("game_new.html", form=form)

            if not selected:
                flash("Seleziona almeno un partecipante.", "danger")
                return render_template("game_new.html", form=form)

            if len(selected) < 2:
                flash(
                    "Seleziona almeno due partecipanti per creare una partita.",
                    "danger",
                )
                return render_template("game_new.html", form=form)

            # Ordine di arrivo (hidden field 'positions' compilato dal JS)
            raw_positions = (request.form.get("positions") or "").strip()
            if not raw_positions:
                flash(
                    "Devi impostare l’ordine di arrivo trascinando i giocatori.",
                    "danger",
                )
                return render_template("game_new.html", form=form)

            try:
                positions = [int(x) for x in raw_positions.split(",") if x]
            except ValueError:
                flash("Formato non valido per l’ordine di arrivo.", "danger")
                return render_template("game_new.html", form=form)

            selected_set = set(selected)
            positions_set = set(positions)

            # Devono coincidere come insiemi e come cardinalità
            if positions_set != selected_set or len(positions) != len(selected):
                flash(
                    "L’ordine di arrivo deve includere tutti e soli i partecipanti selezionati, senza duplicati.",
                    "danger",
                )
                return render_template("game_new.html", form=form)

            # 3) Calcoli torneo
            total_rebuys = sum(rebuy_map.get(pid, 0) for pid in selected)
            total_entries = len(selected) + total_rebuys
            prize_pool = total_entries * buy_in

            if total_entries <= 0:
                flash(
                    "Entrate totali nulle: verifica i partecipanti.",
                    "danger",
                )
                return render_template("game_new.html", form=form)

            # Controllo "soft" coerenza tra vincite inserite e montepremi
            total_manual_prizes = sum(
                prize_map.get(pid, 0.0) for pid in selected
            )
            if round(total_manual_prizes, 2) != round(prize_pool, 2):
                flash(
                    f"Attenzione: la somma delle vincite inserite (€{total_manual_prizes:.2f}) "
                    f"non coincide con il montepremi calcolato (€{prize_pool:.2f}).",
                    "warning",
                )

            # 4) Creazione Game dopo le validazioni
            g = Game(date=date, buy_in=buy_in)
            db.session.add(g)
            db.session.flush()  # per avere g.id

            # Tabella punti base (automatica)
            points_table = compute_points_table(total_entries)

            # Persisti risultati in base all’ordine (1° in cima)
            for rank_index, player_id in enumerate(positions, start=1):
                player_rebuys = rebuy_map.get(player_id, 0)

                # Punti automatici per posizione
                base_points = max(points_table - (rank_index - 1), 0)

                # Override con punti manuali se presenti
                manual_pts = manual_points_map.get(player_id)
                if manual_pts is not None:
                    points = manual_pts
                else:
                    points = base_points

                buy_cost = (1 + player_rebuys) * buy_in

                # Vincita lorda inserita manualmente per quel giocatore
                prize = float(prize_map.get(player_id, 0.0))
                cash_delta = prize - buy_cost

                r = Result(
                    game_id=g.id,
                    player_id=player_id,
                    finish=rank_index,
                    rebuys=player_rebuys,
                    points=points,
                    cash_delta=cash_delta,
                )
                db.session.add(r)

            g.total_entries = total_entries
            g.prize_pool = prize_pool
            db.session.commit()

            flash("Partita creata.", "success")
            return redirect(url_for("game_detail", game_id=g.id))

        # Se POST non passa le validazioni WTForms, mostra gli errori
        if request.method == "POST" and not form.validate():
            for field, errs in form.errors.items():
                for err in errs:
                    flash(f"Errore campo {field}: {err}", "danger")

        return render_template("game_new.html", form=form)

    @app.route("/games/<int:game_id>")
    def game_detail(game_id):
        g = Game.query.get_or_404(game_id)
        results = (
            Result.query.filter_by(game_id=g.id)
            .join(Player, Result.player_id == Player.id)
            .order_by(Result.finish.asc())
            .all()
        )
        return render_template(
            "game_detail.html",
            game=g,
            results=results,
        )

    @app.route("/games/<int:game_id>/delete", methods=["POST"])
    @login_required
    def game_delete(game_id):
        g = Game.query.get_or_404(game_id)
        db.session.delete(g)
        db.session.commit()
        flash("Partita eliminata.", "success")
        return redirect(url_for("games"))

    # --- Auth ----------------------------------------------------------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        form = LoginForm()
        if form.validate_on_submit():
            admin_user = AdminUser()
            if admin_user and check_password_hash(
                admin_user.password_hash, form.password.data
            ):
                login_user(admin_user)
                flash("Accesso eseguito.", "success")
                return redirect(request.args.get("next") or url_for("index"))
            flash("Password errata.", "danger")
        return render_template("login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Disconnesso.", "info")
        return redirect(url_for("index"))

    return app


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True,
    )
