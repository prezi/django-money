import importlib
from django import template
from django.conf import settings
from django.template import TemplateSyntaxError, VariableDoesNotExist
from moneyed import Money

from ..models.fields import MoneyPatched

register = template.Library()


class MoneyLocalizeNode(template.Node):

    def __repr__(self):
        return "<MoneyLocalizeNode %r>" % self.money

    def __init__(self, money=None, amount=None, currency=None, use_l10n=None,
                 var_name=None):

        if money and (amount or currency):
            raise Exception('You can define either "money" or the'
                            ' "amount" and "currency".')

        self.money = money
        self.amount = amount
        self.currency = currency
        self.use_l10n = use_l10n
        self.var_name = var_name

        self.request = template.Variable('request')
        self.country_code = None

    @classmethod
    def handle_token(cls, parser, token):

        tokens = token.contents.split()

        # default value
        var_name = None
        use_l10n = True

        # GET variable var_name
        if len(tokens) > 3:
            if tokens[-2] == 'as':
                var_name = parser.compile_filter(tokens[-1])
                # remove the already used data
                tokens = tokens[0:-2]

        # GET variable use_l10n
        if tokens[-1].lower() in ('on', 'off'):

            if tokens[-1].lower() == 'on':
                use_l10n = True
            else:
                use_l10n = False
            # remove the already used data
            tokens.pop(-1)

        # GET variable money
        if len(tokens) == 2:
            return cls(money=parser.compile_filter(tokens[1]),
                       var_name=var_name, use_l10n=use_l10n)

        # GET variable amount and currency
        if len(tokens) == 3:
            return cls(amount=parser.compile_filter(tokens[1]),
                       currency=parser.compile_filter(tokens[2]),
                       var_name=var_name, use_l10n=use_l10n)

        raise TemplateSyntaxError('Wrong number of input data to the tag.')

    def render(self, context):

        money = self.money.resolve(context) if self.money else None
        amount = self.amount.resolve(context) if self.amount else None
        currency = self.currency.resolve(context) if self.currency else None

        try:
            self.country_code = self.request.resolve(context).country_code if self.request else None
        except VariableDoesNotExist:
            self.country_code = None


        if money is not None:
            if isinstance(money, Money):
                money = MoneyPatched._patch_to_current_class(money)
            else:
                raise TemplateSyntaxError('The variable "money" must be an '
                                          'instance of Money.')

        elif amount is not None and currency is not None:
            money = MoneyPatched(float(amount), str(currency))
        else:
            raise TemplateSyntaxError('You must define both variables: '
                                      'amount and currency.')

        money.use_l10n = self.use_l10n

        if self.var_name is None:
            return self._str_override_currency_sign(money)

        # as <var_name>
        context[self.var_name.token] = money

        return ''

    def _str_override_currency_sign(self, money):
        str_money = unicode(money)
        if hasattr(settings, 'CURRENCY_CONFIG_MODULE'):
            currency_config = importlib.import_module(settings.CURRENCY_CONFIG_MODULE)
            overrides = currency_config.override_currency_by_location

            if self.country_code and self.country_code.upper() in overrides.keys():
                currencies = overrides.get(self.country_code)
                if currencies and str(money.currency) in currencies.keys():
                    values = currencies[str(money.currency)]
                    str_money = str(money).replace(values[0], values[1])

        return str_money


@register.tag
def money_localize(parser, token):
    """
    Usage::

        {% money_localize <money_object> [ on(default) | off ] [as var_name] %}
        {% money_localize <amount> <currency> [ on(default) | off ] [as var_name] %}

    Example:

        The same effect:
        {% money_localize money_object %}
        {% money_localize money_object on %}

        Assignment to a variable:
        {% money_localize money_object on as NEW_MONEY_OBJECT %}

        Formatting the number with currency:
        {% money_localize '4.5' 'USD' %}

    Return::

        MoneyPatched object

    """
    return MoneyLocalizeNode.handle_token(parser, token)
