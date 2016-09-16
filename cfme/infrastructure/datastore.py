""" A model of an Infrastructure Datastore in CFME


:var page: A :py:class:`cfme.web_ui.Region` object describing common elements on the
           Datastores pages.
"""
from functools import partial

from cfme.exceptions import CandidateNotFound, ListAccordionLinkNotFound
from cfme.fixtures import pytest_selenium as sel
from cfme.web_ui import (
    Quadicon, Region, listaccordion as list_acc, toolbar as tb,
    flash, InfoBlock, summary_title, fill
)
from cfme.web_ui.form_buttons import FormButton
from cfme.web_ui.menu import nav
from utils import version
from utils.appliance.endpoints.ui import navigate_to
from utils.log import logger
from utils.pretty import Pretty
from utils.providers import get_crud
from utils.wait import wait_for


details_page = Region(infoblock_type='detail')

page_title_loc = '//div[@id="center_div" or @id="main-content"]//h1'

default_datastore_filter_btn = FormButton('Set the current filter as my default')

cfg_btn = partial(tb.select, 'Configuration')
pol_btn = partial(tb.select, 'Policy')


def nav_to_datastore_through_provider(context):
    navigate_to(context['provider'], 'All')
    list_acc.select('Relationships', 'Datastores', by_title=False, partial=True)
    sel.click(Quadicon(context['datastore'].name, 'datastore'))


nav.add_branch(
    'infrastructure_datastores', {
        'infrastructure_datastore':
        lambda ctx: sel.click(Quadicon(ctx['datastore'].name, 'datastore'))
        if 'provider' not in ctx else nav_to_datastore_through_provider(ctx)
    }
)


class Datastore(Pretty):
    """ Model of an infrastructure datastore in cfme

    Args:
        name: Name of the datastore.
        provider_key: Name of the provider this datastore is attached to.

    Note:
        If given a provider_key, it will navigate through ``Infrastructure/Providers`` instead
        of the direct path through ``Infrastructure/Datastores``.
    """
    pretty_attrs = ['name', 'provider_key']

    def __init__(self, name=None, provider_key=None, type=None):
        self.name = name
        self.type = type
        if provider_key:
            self.provider = get_crud(provider_key)
        else:
            self.provider = None

    def _get_context(self):
        context = {'datastore': self}
        if self.provider:
            context['provider'] = self.provider
        return context

    def delete(self, cancel=True):
        """
        Deletes a datastore from CFME

        Args:
            cancel: Whether to cancel the deletion, defaults to True

        Note:
            Datastore must have 0 hosts and 0 VMs for this to work.
        """
        sel.force_navigate('infrastructure_datastore', context=self._get_context())
        cfg_btn('Remove from the VMDB', invokes_alert=True)
        sel.handle_alert(cancel=cancel)

    def wait_for_delete(self):
        sel.force_navigate('infrastructure_datastores')
        wait_for(lambda: not self.exists, fail_condition=False,
             message="Wait datastore to disappear", num_sec=500, fail_func=sel.refresh)

    def wait_for_appear(self):
        sel.force_navigate('infrastructure_datastores')
        wait_for(lambda: self.exists, fail_condition=False,
             message="Wait datastore to appear", num_sec=1000, fail_func=sel.refresh)

    def load_details(self, refresh=False):
        if not self._on_detail_page():
            logger.debug("load_details: not on details already, navigating")
            sel.force_navigate('infrastructure_datastore', context=self._get_context())
        else:
            logger.debug("load_details: already on details, refreshing")
            if refresh:
                tb.refresh()

    def get_detail(self, *ident):
        """ Gets details from the details infoblock

        The function first ensures that we are on the detail page for the specific datastore.

        Args:
            *ident: An InfoBlock title, followed by the Key name, e.g. "Relationships", "Images"
        Returns: A string representing the contents of the InfoBlock's value.
        """
        self.load_details()
        return details_page.infoblock.text(*ident)

    def _on_detail_page(self):
        """ Returns ``True`` if on the datastore detail page, ``False`` if not."""
        title = version.pick({
            version.LOWEST: '{} ({})'.format(self.name, "Datastore"),
            "5.6": '{} "{}"'.format("Datastore", self.name)})
        try:
            return summary_title() == title
        except AttributeError:
            return False

    def get_hosts(self):
        """ Returns names of hosts (from quadicons) that use this datastore

        Returns: List of strings with names or `[]` if no hosts found.
        """
        if not self._on_hosts_page():
            sel.force_navigate('infrastructure_datastore', context=self._get_context())
            try:
                sel.click(details_page.infoblock.element("Relationships", "Hosts"))
            except sel.NoSuchElementException:
                sel.click(InfoBlock('Relationships', 'Hosts'))
        return [q.name for q in Quadicon.all("host")]

    def _on_hosts_page(self):
        """ Returns ``True`` if on the datastore hosts page, ``False`` if not."""
        return summary_title() == '{} ({})'.format(self.name, "All Registered Hosts")

    def get_vms(self):
        """ Returns names of VMs (from quadicons) that use this datastore

        Returns: List of strings with names or `[]` if no vms found.
        """
        if not self._on_vms_page():
            sel.force_navigate('infrastructure_datastore', context=self._get_context())
            try:
                list_acc.select('Relationships', "VMs", by_title=False, partial=True)
            except (sel.NoSuchElementException, ListAccordionLinkNotFound):
                sel.click(InfoBlock('Relationships', 'Managed VMs'))
        return [q.name for q in Quadicon.all("vm")]

    def _on_vms_page(self):
        """ Returns ``True`` if on the datastore vms page, ``False`` if not."""
        return summary_title() == '{} ({})'.format(self.name, "All Registered VMs")

    def delete_all_attached_vms(self):
        self.load_details()
        sel.click(details_page.infoblock.element("Relationships", "Managed VMs"))
        for q in Quadicon.all('vm'):
            fill(q.checkbox(), True)
        cfg_btn("Remove selected items from the VMDB", invokes_alert=True)
        sel.handle_alert(cancel=False)

    def delete_all_attached_hosts(self):
        self.load_details()
        sel.click(details_page.infoblock.element("Relationships", "Hosts"))
        for q in Quadicon.all('host'):
            fill(q.checkbox(), True)
        path = version.pick({
            version.LOWEST: "Remove Hosts from the VMDB",
            "5.4": "Remove items from the VMDB"})
        cfg_btn(path, invokes_alert=True)
        sel.handle_alert(cancel=False)

    def wait_for_delete_all(self):
        try:
            sel.refresh()
            if sel.is_displayed_text("No Records Found"):
                return True
        except CandidateNotFound:
                return False

    @property
    def exists(self):
        try:
            sel.force_navigate('infrastructure_datastore', context=self._get_context())
            quad = Quadicon(self.name, 'datastore')
            if sel.is_displayed(quad):
                return True
        except sel.NoSuchElementException:
            return False

    def run_smartstate_analysis(self):
        """ Runs smartstate analysis on this host

        Note:
            The host must have valid credentials already set up for this to work.
        """
        sel.force_navigate('infrastructure_datastore', context={
            'datastore': self, 'provider': self.provider})
        tb.select('Configuration', 'Perform SmartState Analysis', invokes_alert=True)
        sel.handle_alert()
        flash.assert_message_contain('"{}": scan successfully initiated'.format(self.name))


def get_all_datastores(do_not_navigate=False):
    """Returns names (from quadicons) of all datastores"""
    if not do_not_navigate:
        sel.force_navigate('infrastructure_datastores')
    return [q.name for q in Quadicon.all("datastore")]
