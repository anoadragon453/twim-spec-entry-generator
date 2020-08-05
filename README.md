# TWIM Spec Entry Generator

Generates Spec entries for TWIM! Makes use of the
[msc-chart-generator](https://github.com/anoadragon453/msc-chart-generator)
library to generate chart images.

## Config

Put your access token into the `github_token = ""` line for now.
I know it's horrible.

## Install

Install python dependencies:

```sh
virtualenv -p python env
source env/bin/activate
pip install -r requirements.txt
```

Install npm dependencies (needed for exporting images... yeah):

```sh
npm install -g electron@6.1.4 orca
```

## Run

```sh
python ./main.py
```
