name: Auto Update & Rebuild Site (4x Daily IST)

on:
  schedule:
    - cron: '0 3 * * *'
    - cron: '30 6 * * *'
    - cron: '0 12 * * *'
    - cron: '30 15 * * *'
  workflow_dispatch:
  push:
    paths:
      - 'templates/**'
      - 'data/**'

permissions:
  contents: write

jobs:
  update-and-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          if [ -f scripts/daily_auto_update.py ]; then python3 scripts/daily_auto_update.py; else python3 Scripts/daily_auto_update.py; fi
      - run: |
          if [ -f scripts/build_site.py ]; then python3 scripts/build_site.py; else python3 Scripts/build_site.py; fi
      - run: |
          git config user.name "Latest Job Alert Bot"
          git config user.email "bot@latestjobalert.local"
          git add -A
          git diff --staged --quiet || git commit -m "Auto-update Latest Job Alert content & rebuild"
          git push
