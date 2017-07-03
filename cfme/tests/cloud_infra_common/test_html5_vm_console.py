import pytest
import imghdr
import re

from cfme.cloud.provider.openstack import OpenStackProvider
from cfme.configure.configuration import VMwareConsoleSupport
from cfme.infrastructure.provider.rhevm import RHEVMProvider
from cfme.infrastructure.provider.virtualcenter import VMwareProvider
from cfme.common.vm import VM
from utils import testgen, version
from utils.appliance.implementations.ui import navigate_to
from utils.conf import credentials
from utils.log import logger

pytestmark = pytest.mark.usefixtures('setup_provider')

pytest_generate_tests = testgen.generate(
    [OpenStackProvider, RHEVMProvider, VMwareProvider],
    scope='module'
)


@pytest.fixture(scope="function")
def vm_obj(request, provider, setup_provider, small_template, vm_name):
    vm_obj = VM.factory(vm_name, provider, template_name=small_template)

    @request.addfinalizer
    def _delete_vm():
        try:
            vm_obj.delete_from_provider()
        except Exception:
            logger.warning("Failed to delete vm `{}`.".format(vm_obj.name))

    vm_obj.create_on_provider(timeout=2400, find_in_cfme=True, allow_skip="default")
    return vm_obj


def _configureVMwareConsoleForTest(appliance):
    '''
    Configure VMware Console to use VNC which is what is required
    for the HTML5 console.
    '''

    navigate_to(appliance.server, 'Server')

    settings_pg = VMwareConsoleSupport(
        appliance=appliance,
        console_type='VNC',
    )
    settings_pg.update()


@pytest.mark.uncollectif(lambda: version.current_version() < '5.8', reason='Only valid for >= 5.8')
def test_html5_vm_console(appliance, provider, vm_obj):
    '''
    Tests the HTML5 console support for a particular provider.   The supported providers are:

        VMware
        Openstack
        RHV

    For a given provider, and a given VM, the console will be opened, and then:

        - The console's status will be checked.
        - A command that creates a file will be sent through the console.
        - Using ssh we will check that the command worked (i.e. that the file
          was created.
    '''
    if provider.one_of(VMwareProvider):
        _configureVMwareConsoleForTest(appliance)

    vm_obj.open_console(console='VM Console')
    assert vm_obj.vm_console is not None, 'VMConsole object should be created'

    vm_console = vm_obj.vm_console

    # If the banner/connection-status element exists we can get
    # the connection status text and if the console is healthy, it should connect.
    assert vm_console.wait_for_connect() is True, "VM Console did not reach 'connected' state"

    # Get the login screen image, and make sure it is a png file:
    screen = vm_console.get_screen()
    assert imghdr.what('', screen) == 'png'

    # Try to login:
    # XXX: This is hard coded, we need to add some new yaml to track the
    #      template credentials.
    vm_console.send_keys("cirros\n")
    vm_console.send_keys("cubswin:)\n")

    # create file on system
    vm_console.send_keys("touch /tmp/blather\n")

    # Test pressing ctrl-alt-delete...we should be able to get a new connect after doing this:
    vm_console.send_ctrl_alt_delete()
    vm_console.wait_for_connect()
