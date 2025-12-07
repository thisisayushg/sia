# Configure a new logger called "MCPClient" with debug level
import logging
logger = logging.getLogger("MCPClient")
logger.setLevel(logging.DEBUG)

# Add file handler to log to a file named 'mcp_client.log'
file_handler = logging.FileHandler('mcp_client.log')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(file_handler)

# Add Console handler with Log Info level
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)
logger.addHandler(console_handler)
