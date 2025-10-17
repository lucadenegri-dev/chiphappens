# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectMultipleField, FloatField, DateField, PasswordField
from wtforms.validators import DataRequired, Length, NumberRange
from wtforms.widgets import ListWidget, CheckboxInput
from wtforms import Field

class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

class PlayerForm(FlaskForm):
    name = StringField('Nome', validators=[DataRequired(), Length(min=2, max=80)])
    submit = SubmitField('Aggiungi')

class LoginForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Accedi')

class GameCreateForm(FlaskForm):
    date = DateField('Data', format='%Y-%m-%d', description='YYYY-MM-DD')
    buy_in = FloatField('Buy-in',
                        validators=[DataRequired(), NumberRange(min=0.01, message='Il buy-in deve essere > 0')])
    participants = MultiCheckboxField('Partecipanti', coerce=int)
    # positions: comma-separated list of player IDs in finishing order
    positions = StringField('Ordine di arrivo (IDs separati da virgola, primo=1°)', validators=[DataRequired()])
    # rebuys: sent as dynamic dict via request.form with key 'rebuy_<player_id>'
    submit = SubmitField('Crea partita')

    @property
    def rebuys(self):
        # Build a dict {player_id: rebuy_count}
        data = {}
        for k, v in (dict(self._formdata) if self._formdata else {}).items():
            if k.startswith('rebuy_'):
                try:
                    pid = int(k.split('_', 1)[1])
                    data[pid] = int(v) if v not in (None, '',) else 0
                except Exception:
                    pass
        return data