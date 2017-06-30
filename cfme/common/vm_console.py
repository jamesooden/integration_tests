# -*- coding: utf-8 -*-
"""Module containing classes with common behaviour for consoles of both VMs and Instances of all types."""

import base64
import re

from utils.log import logger
from utils.pretty import Pretty
from wait_for import wait_for

banner_id = 'noVNC_status'
canvas_id = 'noVNC_canvas'
ctrl_alt_del_id = 'sendCtrlAltDelButton'

class VMConsole(Pretty):
    """
    Class to manage the VM Console.   Presently, only support HTML5 Console.
    """
    pretty_attrs = ['appliance_handle', 'browser', 'console_handle', 'name']

    def __init__(self, name, selenium, console_handle, appliance_handle, provider):
        self.name = name
        self.selenium = selenium
        self.console_handle = console_handle
        self.appliance_handle = appliance_handle
        self.provider = provider

    ###
    # Methods
    #
    def get_banner(self):
        '''
        Gets the text of the banner above the console screen.
        '''
        self.switch_to_console()
        text = self.selenium.find_element_by_id(banner_id).text
        logger.info('Read following text from console banner: {}'.format(text))
        self.switch_to_appliance()
        return text

    def get_screen(self):
        '''
        Retrieves the bit map from the canvas widget that represents the
        console screen.   Returns it as a binary string.

        Implementation:
        The canvas tag has a method toDataURL() which one can use in javascript to
        obtain the canvas image  base64 encoded.   Examples of how to do this can be
        seen here:

            https://qxf2.com/blog/selenium-html5-canvas-verify-what-was-drawn/
            https://stackoverflow.com/questions/38316402/how-to-save-a-canvas-as-png-in-selenium
        '''
        self.switch_to_console()

        # Get the canvas element
        canvas = self.selenium.find_element_by_id(canvas_id)

        # Now run some java script to get the contents of the canvas element
        # base 64 encoded.
        image_base64_url = self.selenium.execute_script(
            "return arguments[0].toDataURL('image/png');",
            canvas
        )

        # The results will look like:
        #
        #   data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAfQAAABkCAYAAABwx8J9AA...
        #
        # So parse out the data from the non image data from the URL:
        image_base64 = image_base64_url.split(",")[1]

        # Now convert to binary:
        image_png = base64.b64decode(image_base64)

        self.switch_to_appliance()
        return image_png

    def is_connected(self):
        '''
        Waits for the banner on the console to say the console is connected.
        '''
        banner = self.get_banner()
        return re.match('Connected', banner) is not None

    def send_keys(self, text):
        '''
        Sends text to the console.
        '''
        self.switch_to_console()
        canvas = self.selenium.find_element_by_id(canvas_id)
        canvas.send_keys(text)
        self.switch_to_appliance()

    def send_ctrl_alt_delete(self):
        '''
        Presses the ctrl-alt-delete button in the console
        tab.
        '''
        self.switch_to_console()
        ctrl_alt_del_btn = self.selenium.find_element_by_id(ctrl_alt_del_id)
        ctrl_alt_del_btn.click()
        self.switch_to_appliance()

    def switch_to_appliance(self):
        '''
        Switches focus to appliance tab/window.
        '''
        logger.info("Switching to appliance: window handle = {}".format(self.appliance_handle))
        self.selenium.switch_to_window(self.appliance_handle)

    def switch_to_console(self):
        '''
        Switches focus to console tab/window.
        '''
        logger.info("Switching to console: window handle = {}".format(self.console_handle))
        self.selenium.switch_to_window(self.console_handle)

    def wait_for_connect(self, timeout=5):
        '''
        Wait's for as long as the specified/default timeout for the console to
        be connected.
        '''
        wait_for(func=lambda: self.is_connected(),
                 delay=1,
                 num_sec=timeout)

