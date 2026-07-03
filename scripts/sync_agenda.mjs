- name: Sincronizar Agenda Tática (grava iniciativas no D1)
        if: ${{ github.event.inputs.deploy != 'false' }}
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
        run: |
          export CLOUDFLARE_API_TOKEN="$(printf %s "$CLOUDFLARE_API_TOKEN" | tr -d '[:space:]')"
          export CLOUDFLARE_ACCOUNT_ID="$(printf %s "$CLOUDFLARE_ACCOUNT_ID" | tr -d '[:space:]')"
          node scripts/sync_agenda.mjs data/freq_multi.json > agenda_week.sql
          echo "Linhas SQL: $(wc -l < agenda_week.sql)"; head -c 300 agenda_week.sql; echo
          npx --yes wrangler@3 d1 execute nadarte_agenda --remote --file=agenda_week.sql
