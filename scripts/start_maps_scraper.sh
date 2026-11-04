#!/usr/bin/env bash
# ==============================================================================
# NorthWay 2.0 - Inicializador do NorthWay Prospector (PT-BR + Mapa Interativo)
# ==============================================================================

set -e

CONTAINER_NAME="northway-maps-scraper"
PORTAL_PORT="8080"
ENGINE_PORT="8081"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${PROJECT_ROOT}/scraper_data"

echo "🚀 Iniciando NorthWay Prospector (Interface em Português + Mapa Interativo)..."

# 1. Criar diretório de dados persistentes
mkdir -p "${DATA_DIR}"

# 2. Verificar se o Docker está rodando
if ! docker info >/dev/null 2>&1; then
    echo "⚠️  O Docker Desktop não está em execução."
    echo "Iniciando o Docker Desktop..."
    open -a Docker || true
    echo "Aguardando o daemon do Docker inicializar..."
    for i in {1..30}; do
        if docker info >/dev/null 2>&1; then
            echo "✅ Docker inicializado."
            break
        fi
        sleep 2
    done
fi

# 3. Configurar o container do motor do Scraper na porta 8081 (se o Docker estiver ativo)
if docker info >/dev/null 2>&1; then
    # Se existir um container antigo usando a porta 8080 diretamente, recriar na 8081
    if docker ps -a --format '{{.Names}} {{.Ports}}' | grep "${CONTAINER_NAME}" | grep -q ":8080->8080"; then
        echo "🔄 Atualizando porta do motor Docker para ${ENGINE_PORT}..."
        docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi

    if [ "$(docker ps -q -f name=${CONTAINER_NAME})" ]; then
        echo "✅ Motor Docker já está ativo na porta ${ENGINE_PORT}."
    elif [ "$(docker ps -aq -f status=exited -f name=${CONTAINER_NAME})" ]; then
        echo "🔄 Reiniciando motor Docker existente..."
        docker start "${CONTAINER_NAME}" >/dev/null
    else
        echo "📦 Criando e iniciando o motor ${CONTAINER_NAME} na porta ${ENGINE_PORT}..."
        docker run -d \
          --name "${CONTAINER_NAME}" \
          -p "${ENGINE_PORT}:8080" \
          -v "${DATA_DIR}:/gmapsdata" \
          --restart unless-stopped \
          gosom/google-maps-scraper \
          -data-folder /gmapsdata \
          -web >/dev/null
    fi
fi

# 4. Iniciar o Portal NorthWay em Português + Mapa Interativo na porta 8080
if lsof -Pi :${PORTAL_PORT} -sTCP:LISTEN -t >/dev/null 2>&1; then
    kill -9 $(lsof -Pi :${PORTAL_PORT} -sTCP:LISTEN -t) >/dev/null 2>&1 || true
fi

nohup python3 "${PROJECT_ROOT}/scripts/scraper_portal.py" >/tmp/northway_scraper_portal.log 2>&1 &
sleep 1

echo "--------------------------------------------------------"
echo "🎉 NorthWay Prospector (PT-BR + Mapa) iniciado com sucesso!"
echo "🌐 Painel Visual com Mapa: http://localhost:${PORTAL_PORT}"
echo "⚙️  Motor Docker (API):     http://localhost:${ENGINE_PORT}"
echo "📁 Pasta de dados:         ${DATA_DIR}"
echo "--------------------------------------------------------"

open "http://localhost:${PORTAL_PORT}"
