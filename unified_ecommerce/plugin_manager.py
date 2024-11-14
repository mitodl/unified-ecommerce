"""Plugin manager for the Unified Ecommerce app."""

import pluggy

from payments import hookspecs as payments_hookspecs
from payments.hooks import basket_add as payments_basket_add
from payments.hooks import post_sale as payments_post_sale


def get_plugin_manager():
    """Return the plugin manager for the app."""

    pm = pluggy.PluginManager("unified_ecommerce")

    pm.add_hookspecs(payments_hookspecs)
    pm.register(payments_post_sale.PostSaleSendEmails())
    pm.register(payments_post_sale.IntegratedSystemWebhooks())
    pm.register(payments_basket_add.CustomerVerificationHooks())

    pm.load_setuptools_entrypoints("unified_ecommerce")
    return pm
