import json
from burp import IBurpExtender, IProxyListener, IExtensionStateListener, ITab
from javax.swing import JPanel, JOptionPane, JLabel, JTextField, JButton, JScrollPane, Box, BoxLayout, JTextArea, \
    SwingConstants, JComboBox
from java.awt import Dimension
from threading import Thread
from consts import OPENAI_URL, DEFAULT_PROMPT, ORIGINAL_PATH, SEPERATOR


class BurpExtender(IBurpExtender, ITab, IProxyListener, IExtensionStateListener):

    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        self._callbacks.setExtensionName("BurpGPT")

        # Create top panel with domain, key, and version components
        top_panel = JPanel()
        top_panel.setLayout(BoxLayout(top_panel, BoxLayout.X_AXIS))

        domain_panel = JPanel()
        self._domain_label = JLabel("Domain:")
        self._domains = self.get_hosts()
        self._domain_text = JComboBox(list(self._domains))
        domain_panel.add(self._domain_label)
        domain_panel.add(self._domain_text)
        top_panel.add(domain_panel)

        api_key_panel = JPanel()
        self._api_key_label = JLabel("API Key:")
        self._api_key_text = JTextField(35)
        api_key_panel.add(self._api_key_label)
        api_key_panel.add(self._api_key_text)
        top_panel.add(api_key_panel)

        gpt_version_panel = JPanel()
        self._gpt_version_label = JLabel("GPT Version:")
        self._gpt_version_choice = JComboBox(["gpt-4", "gpt-3.5-turbo"])
        gpt_version_panel.add(self._gpt_version_label)
        gpt_version_panel.add(self._gpt_version_choice)
        top_panel.add(gpt_version_panel)

        # Create middle panel with prompt and submit button components
        middle_panel = JPanel()
        middle_panel.setLayout(BoxLayout(middle_panel, BoxLayout.Y_AXIS))
        self._prompt_label = JLabel("Optional Prompt:")
        self._prompt_text = JTextArea()
        self._prompt_text.setLineWrap(True)
        self._prompt_text.setWrapStyleWord(True)
        middle_panel.add(self._prompt_label)
        middle_panel.add(self._prompt_text)
        self._submit_button = JButton("Submit", actionPerformed=self.submit_data)
        middle_panel.add(self._submit_button)

        # Create bottom panel with output components
        bottom_panel = JPanel()
        bottom_panel.setLayout(BoxLayout(bottom_panel, BoxLayout.Y_AXIS))
        self._output_label = JLabel("ChatGPT Answer:")
        self._output_text = JTextArea(30, 100)
        self._output_text.setEditable(False)
        self._output_text.setLineWrap(True)
        self._output_text.setWrapStyleWord(True)
        scroll = JScrollPane(self._output_text)
        bottom_panel.add(self._output_label)
        bottom_panel.add(scroll)

        # Add panels to main panel and register tab
        self._panel = JPanel()
        self._panel.setLayout(BoxLayout(self._panel, BoxLayout.Y_AXIS))
        self._panel.add(top_panel)
        self._panel.add(middle_panel)
        self._panel.add(bottom_panel)
        callbacks.addSuiteTab(self)
        callbacks.registerProxyListener(self)
        callbacks.registerExtensionStateListener(self)

    def getTabCaption(self):
        return "BurpGPT"

    def getUiComponent(self):
        return self._panel

    def processProxyMessage(self, messageIsRequest, message):
        if messageIsRequest:
            http_service = message.getMessageInfo().getHttpService()
            if http_service.getHost() not in self._domains:
                self._domain_text.addItem(http_service.getHost())
                self._domains.add(http_service.getHost())

    def extensionUnloaded(self):
        self._callbacks.removeProxyListener(self)

    def get_hosts(self):
        """
        Function return all domains from http history
        :return: set of domains
        """
        res = set()
        http_traffic = self._callbacks.getProxyHistory()
        for traffic in http_traffic:
            http_service = traffic.getHttpService()
            res.add((http_service.getHost()))
        return set(sorted(list(res)))

    def submit_data(self, event):
        """
        Function extract user data and analyze the http requests and send it to ChatGPT
        :return:
        """
        domain, api_key, prompt, chat_version = self.get_user_data()
        # Get all requests and responses from history
        http_request_and_response = self.analyze_http_traffic(domain)
        if http_request_and_response:
            # Run the get_chatgpt_answer function in a separate thread
            def run():
                self._output_text.setText("")
                chat_gpt_answer = self.get_chatgpt_answer(prompt, api_key, http_request_and_response, chat_version)
                # Update the UI with the answer
                self._output_text.setText(chat_gpt_answer)
                JOptionPane.showMessageDialog(None, "ChatGPT completed successfully.", "Success",
                                              JOptionPane.INFORMATION_MESSAGE)

            thread = Thread(target=run)
            thread.start()

            # Show a message to the user while the function is running
            JOptionPane.showMessageDialog(None, "ChatGPT is running. Please wait...", "Information",
                                          JOptionPane.INFORMATION_MESSAGE)
        else:
            self._output_text.setText("Cant find the domain {} in the History".format(domain))

    def analyze_http_traffic(self, domain):
        """
        Function go over all requests and response and convert them to string for send to ChatGPT
        :param domain: The specified domain we want to go over
        :return: List of http data
        """
        http_traffic = self._callbacks.getProxyHistory()
        http_request_and_response = []
        for traffic in http_traffic:
            http_service = traffic.getHttpService()
            host = http_service.getHost()
            if domain in host:
                res = self.analyze_data(traffic, 'Request')
                resp = self.analyze_data(traffic, 'Response')
                if res and resp:
                    http_request_and_response.append(res + "\n" + resp)
        return http_request_and_response

    def get_user_data(self):
        """
        Function extract the user data
        :return:
        """
        domain = self._domain_text.getSelectedItem()
        api_key = self._api_key_text.getText()
        prompt = self._prompt_text.getText()
        if not prompt:
            prompt = DEFAULT_PROMPT
        chat_version = self._gpt_version_choice.getSelectedItem()
        return domain, api_key, prompt, chat_version

    def analyze_data(self, traffic, method):
        """
        Function analyze the http data
        :param traffic: Http traffic
        :param method: the method we want to analyze
        :return:
        """
        data_http = ""
        if method == "Request":
            data = traffic.getRequest()
            if data:
                data_http = self._helpers.analyzeRequest(data)
        else:
            data = traffic.getResponse()
            if data:
                data_http = self._helpers.analyzeResponse(data)
        if data_http:
            headers = list(data_http.getHeaders() or [])
            headers_str = '\n'.join([str(x) for x in headers])
            body = data[data_http.getBodyOffset():].tostring()
            return headers_str + body

    def get_chatgpt_answer(self, prompt, api_key, http_request_and_response, gpt_version):
        """
        :param prompt: The Prompt that will be sent to ChatGPT
        :param api_key: OpenAI API key
        :param http_request_and_response: List of all the HTTP requests and responses
        :param gpt_version: ChatGPT version
        :return: ChatGPT answer
        """
        headers = ["POST {} HTTP/2.0".format(ORIGINAL_PATH), "Host: " + OPENAI_URL,
                   "Authorization: Bearer {}".format(api_key), "Content-Type: application/json"]
        try:
            http_request_and_response_str = SEPERATOR.join([str(x) for x in http_request_and_response])
        except Exception as e:
            return "Error converting the http data to string {}".format(str(e))
        body = {"messages": [{"content": prompt + "{}".format(http_request_and_response_str), "role": "system"}],
                "model": gpt_version}
        http_service = self._helpers.buildHttpService(OPENAI_URL, 443, True)
        request = self._helpers.buildHttpMessage(headers, self._helpers.stringToBytes(json.dumps(body)))
        res = self._callbacks.makeHttpRequest(http_service, request)
        data = res.getResponse()
        if data:
            data_http = self._helpers.analyzeResponse(data)
            body = data[data_http.getBodyOffset():].tostring()
            json_body = json.loads(body)
            if "error" in json_body:
                return json_body.get('error').get('message')
            return json_body.get('choices')[0].get('message').get('content')
        else:
            return "ChatGPT did not return any answer"
