#!/usr/bin/env bash
# ==============================================================================
# NorthWay 2.0 - CLI Direct Lead Scraper
# Exemplo de uso:
#   ./scripts/scrape_leads.sh "odontologia curitiba batel"
# ==============================================================================

set -e

QUERY="$1"
DEPTH="${2:-3}" # profundidade de scroll (1 = ~20 leads, 3 = ~60 leads, 5 = ~100 leads)

if [ -z "$QUERY" ]; then
    echo "❌ Uso: $0 \"termo de busca\" [profundidade_scroll]"
    echo "Exemplo: $0 \"imobiliarias em florianopolis centro\" 3"
    exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${PROJECT_ROOT}/scraper_data"
mkdir -p "${OUTPUT_DIR}"

QUERY_FILE="${OUTPUT_DIR}/current_query.txt"
RESULT_FILE="${OUTPUT_DIR}/results_$(date +%Y%m%d_%H%M%S).json"
LATEST_FILE="${OUTPUT_DIR}/latest_leads.json"

echo "$QUERY" > "$QUERY_FILE"

echo "🔎 Buscando leads no Google Maps para: '$QUERY' (depth=$DEPTH)..."
echo "⏳ Extraindo dados com Playwright e buscando emails em sites..."

docker run --rm \
  -v "${OUTPUT_DIR}:/data" \
  gosom/google-maps-scraper \
  -input /data/current_query.txt \
  -results "/data/$(basename "$RESULT_FILE")" \
  -depth "$DEPTH" \
  -lang "pt-BR" \
  -email \
  -json \
  -exit-on-inactivity 2m

if [ -f "$RESULT_FILE" ]; then
    cp "$RESULT_FILE" "$LATEST_FILE"
    LEAD_COUNT=$(grep -o '"title":' "$RESULT_FILE" | wc -l | tr -d ' ')
    echo "--------------------------------------------------------"
    echo "🎉 Raspagem concluída!"
    echo "📊 Total aproximado de empresas: ${LEAD_COUNT}"
    echo "📁 Arquivo salvo em: $RESULT_FILE"
    echo "📁 Cópia recente em: $LATEST_FILE"
    echo "👉 Agora vá em 'Prospecção Ativa' no NorthWay CRM e use 'Importar do Scraper'!"
    echo "--------------------------------------------------------"
else
    echo "⚠️ Nenhum resultado gerado."
fi
