import argparse
import logging
import signal

import requests
import time

import yaml
import pyhap.accessory
import pyhap.accessory_driver

__import__('accessories', globals(), level=1, fromlist=['*'])
# ^^^ from .accessories import *    , but without polluting the namespace
from .accessories._registry import accessory_registry


parser = argparse.ArgumentParser(description='Velbus HomeKit bridge',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('--persist-file', default="accessory.state",
                    help="File to store pairing info in")
parser.add_argument('--logfile', help="Log to the given file", type=str)
parser.add_argument('--verbose', help="Enable verbose mode", action='store_true')
parser.add_argument('--debug', help="Enable debug mode", action='store_true')
parser.add_argument('base_url', help="Base URL for Velbus REST interface provided by velbuspy")
parser.add_argument('controls_file', help="YAML file describing the available controls. "
                                          "If this stats with http(s)://, it is interpreted as a URL")

args = parser.parse_args()


logging.getLogger(None).setLevel(logging.WARNING)
logging.Formatter.converter = time.gmtime

if args.verbose:
    logging.getLogger(None).setLevel(logging.INFO)
if args.debug:
    logging.getLogger(None).setLevel(logging.DEBUG)

if args.logfile:
    log_file_handler = logging.FileHandler(args.logfile)
else:
    log_file_handler = logging.StreamHandler()
log_file_handler.setFormatter(logging.Formatter(
    fmt="%(asctime)sZ [%(name)s %(levelname)s] %(message)s"
))
logging.getLogger(None).addHandler(log_file_handler)


logger = logging.getLogger(__name__)

# Print loaded modules
logger.info("Loaded Accessories:")
for type_, icon in sorted(accessory_registry.keys()):
    logger.info(f" - {type_}, {icon} => {accessory_registry[(type_, icon)].__name__}")


if args.controls_file.startswith("http://") or \
        args.controls_file.startswith("https://"):
    resp = requests.get(args.controls_file)
    if resp.status_code != 200:
        raise ValueError(f"Could not fetch URL `{args.controls_file}`: {resp.reason}")
    config = resp.content.decode('utf-8')
    config = yaml.safe_load(config)
else:
    with open(args.controls_file, "r") as f:
        config = yaml.safe_load(f.read())

if len(config.get('controls', [])) == 0:
    raise ValueError("Could not find `controls` in config file")

driver = pyhap.accessory_driver.AccessoryDriver(persist_file=args.persist_file)

bridge = pyhap.accessory.Bridge(driver, 'Velbus bridge')
driver.add_accessory(accessory=bridge)

for name, control in config['controls'].items():
    type_ = control['type']
    icon = control['icon']
    try:
        cls = accessory_registry[(type_, icon)]
    except KeyError:
        logger.warning(f"Control {name!r} (type={type_!r}, icon={icon!r}) not supported, ignoring...")
        continue

    acc = cls(
        driver=driver,
        display_name=name,
        velbus_base_url=args.base_url,
        velbus_module_address=control['address'][0],
        velbus_module_channel=control['address'][1],
        aid=control['address'][0] * 256 + control['address'][1],  # Generate persistent AID
    )
    bridge.add_accessory(acc)

# We want SIGTERM (terminate) to be handled by the driver itself,
# so that it can gracefully stop the accessory, server and advertising.
signal.signal(signal.SIGTERM, driver.signal_handler)

# Start it!
driver.start()
