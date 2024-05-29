# ctbph-rank-daily

A way to stalk players that are active (on osu!catch PH leaderboards), on a daily basis!

Powered by Github Actions

## Installation / Running

This is tested to run on Python 3.12.3

```
# clone the repo
git clone https://github.com/0x4kgi/ctbph-rank-daily
cd ctbph-rank-daily

# you can skip this but I highly recommend using venv
# adjust venv activation depending on your environment
python -m venv venv
venv/Scripts/activate

# install required libraries
pip install -r requirements.txt

# setup .env, replace xxx with your tokens
echo "OSU_CLIENT_ID=xxx" >> .env
echo "OSU_CLIENT_SECRET=xxx" >> .env

# see the commands
python leaderboard_scrape.py --help

# a test run to see if things works
# a folder named tests/ should appear
python leaderboard_scrape.py --test
```