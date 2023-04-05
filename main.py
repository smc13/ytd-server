from flask import Flask, request, jsonify
import yt_dlp
import yaml
import fnmatch
import asyncio
import os
import argparse
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from urllib.parse import urlparse
from collections import ChainMap
from pathlib import PurePath
from urllib.parse import urlparse

app = Flask(__name__)

tasks = []

parser = argparse.ArgumentParser()
parser.add_arguments("--config", "-c", help="Path to config file", default="config.yml")

args = parser.parse_args()
config_path = args.config

if not os.path.exists(config_path):
  print("No config.yml file found. Please create one before running this script.")
  os.exit(1)

class ConfigFileHandler(FileSystemEventHandler):
  def on_modified(self, event):
    print("Config file modified")
    global config
    with open(config_path, "r") as f:
      config = yaml.safe_load(f)

with open(config_path, "r") as f:
  config = yaml.safe_load(f)

observer = Observer()
observer.schedule(ConfigFileHandler(), path="./config.yml", recursive=False)
observer.start()

@app.route("/download", methods=["POST"])
async def download():
  request.get_json(force=True)

  url = r"{0}".format(request.json.get("url"))
  if not url:
    return "No URL provided", 400

  opts = getOpts(url)

  print(f"Downloading {url} with options {opts}")
  asyncio.create_task(downloadUrl(url, opts))

  return jsonify({ "message": "download attempt started" }), 200

def getOpts(url):
  default = config.get("default", {})
  domain = get_domain_config(url)

  if domain == {}:
    print(f"could not find config for {url}")

  opts = dict(ChainMap(domain.get("opts", {}), default.get("opts", {})))

  fileName = domain.get("filename", "")
  if fileName == "":
    fileName = default.get("filename", "%(title)s.%(ext)s")

  baseOutput = default.get("output", ".")
  domainOutput = domain.get("output", "")
  output = PurePath(baseOutput, domainOutput, fileName)

  print(f"Outputting file to {output}")
  opts["outtmpl"] = str(output)

  return opts

def merge_dicts(d1, d2):
  """
  Recursively merge two dictionaries. If both values are dictionaries, merge them recursively.
  If one value is not a dictionary, overwrite it with the other value.
  """
  if not d2:
    return d1

  result = d1.copy()
  for k, v in d2.items():
      if k in result and isinstance(result[k], dict) and isinstance(v, dict):
          result[k] = merge_dicts(result[k], v)
      else:
          result[k] = v

  return result

def get_domain_config(url):
  parsed = urlparse(url)
  domain = parsed.netloc
  if domain.startswith("www."):
    domain = domain[4:]
  full_path = domain + parsed.path

  domain_keys = config.get("domains", {}).keys()
  opts = {}

  for key in domain_keys:
    if fnmatch.fnmatch(full_path, key) or fnmatch.fnmatch(domain, key):
      print(f"Found config options for \"{key}\"")
      opts = merge_dicts(config["domains"][key], opts)

  return opts

async def downloadUrl(url, opts):
  loop = asyncio.get_event_loop()
  try:
    with yt_dlp.YoutubeDL(opts) as ydl:
      info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=True))
      meta = ydl.sanitize_info(info)
  except yt_dlp.utils.DownloadError as e:
    print(f"Error downloading {url}: {e}")
    meta = { "message": str(e) }
  except FileExistsError as e:
    print(f"File already exists: {e}")
    meta = { "message": str(e) }

  return meta


if __name__ == "__main__":
  print("Starting server on port 3241")
  app.run(debug=False, port=3241, host="0.0.0.0")