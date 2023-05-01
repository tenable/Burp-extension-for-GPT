SEPERATOR = "```SEPERATOR```"
DEFAULT_PROMPT = """
Act like a security professional and explain to me in one paragraph the following HTTP request and response.\n
Each request and response is divided by the word {} \n
In addition, please create a numbered list of all security issues you find and  include potential fix (mitigation).\n
Output in the format of risk: security issue Fix: mitigation
""".format(SEPERATOR)

OPENAI_URL = "api.openai.com"
ORIGINAL_PATH = "/v1/chat/completions"


