# Publicação candidata na VPS existente

Estado: **preparado, ainda não instalado nem testado na VPS**. A aprovação local não substitui a homologação do servidor.

O Radar novo roda sozinho na porta local 8504; `gm-analytics` e as portas 8501/8502/8503 continuam como estão. SmartBuy e Estoque também permanecem em seus serviços atuais. A imagem nova lê os Parquets já extraídos; não possui credenciais do Cronos e não inicia extrações. Não usar `scripts/start-all.sh`, `start-docker.sh` nem `docker-compose down` para esta publicação.

1. Devolver a saída de `deploy/radar/inspecionar_vps_canvas_20261022.sh`, incluído neste pacote, para confirmar o projeto realmente instalado, o destino do túnel e os dados que precisam ser preservados. A imagem da VPS pode ser diferente do código do notebook.
2. Guardar o commit atual da VPS, a identificação/digest da imagem, o Compose em uso e o `/etc/cloudflared/config.yml`. Não copiar os bancos do notebook para a VPS. Se o servidor ainda usa `usuarios.parquet`, migrar **as contas do servidor** em uma etapa separada e conferir senhas preservadas, quantidade de contas e integridade antes de alterar a rota.
3. Fazer backup consistente do SQLite de acessos e do SQLite de metas/equipe com a API `sqlite3.Connection.backup`. Uma cópia avulsa do arquivo principal pode perder transações ainda no WAL. Guardar também caches completos, fora da imagem. Testar a restauração em diretório temporário e executar `PRAGMA integrity_check` na cópia restaurada.
4. Sincronizar o código revisado e versionado com a VPS, sem `.env`, cache ou dados pessoais. Definir `RADAR_CACHE_HOST` e `RADAR_DADOS_HOST` como caminhos absolutos reais. Conferir a disponibilidade da porta 8504 e o acesso de leitura ao cache e de escrita aos dados pelo UID/GID 10001. Não executar `chown -R` no projeto todo; ajustar somente a pasta destinada aos dados persistentes depois de confirmar seus usuários atuais.
5. Montar e iniciar **apenas o serviço novo**, usando `deploy/radar/compose.yml`. A pasta de dados deve conter as bases preservadas e conferidas do servidor antes do primeiro acesso. O serviço recusa uma pasta ou base ausente. O diretório de cache é montado somente para leitura; as atualizações autorizadas continuam sendo produzidas pelo processo de extração já existente.
6. Homologar pela porta local com encaminhamento SSH `ssh -L 8505:127.0.0.1:8504 USUARIO@VPS`, abrindo `http://localhost:8505`. Não abrir a porta no firewall nem alterar DNS. Validar login, primeiro acesso, reset de senha, gestão, supervisão, vendedora, filtros, ABC, metas e PDF. Contas iguais em instalações paralelas podem ter sessões diferentes; use contas de teste autorizadas.
7. Medir antes/depois: CPU e memória por container (`docker stats --no-stream`); estado e reinícios; tempo de resposta HTTP e, separadamente, tempo até o painel ficar utilizável no navegador. Executar 20 acessos simultâneos e uma rodada de margem com 30, incluindo PDFs e metas concorrentes. O teste HTTP da página inicial sozinho não comprova capacidade do Streamlit. Comparar com os tempos locais registrados em `VALIDACAO.md`.
8. Testar indisponibilidade do ERP mantendo o cache existente, atualização atômica de cache, reinício do serviço novo e recuperação de sessão. Com carteira/histórico de snapshots diferentes, a tela deve recusar a análise até haver uma dupla consistente. Conferir novamente os indicadores conciliados com o Cronos usando o relatório já salvo, sem nova consulta.
9. Somente com os testes aprovados, apontar **apenas** `radar.gmlimpeza.net` no túnel para `http://127.0.0.1:8504`. Preservar as demais regras e a regra final. Validar as regras e recarregar o serviço usando o mecanismo realmente suportado no servidor. Revalidar o domínio, WebSocket, PDFs, sessões e os outros sistemas.

## Retorno

Se a nova interface falhar, restaurar o destino anterior do hostname Radar no túnel (o inventário precisa confirmar se ainda é 8502), validar as regras e reaplicar a configuração. O `gm-analytics` antigo não foi removido. Não restaurar um banco antigo por cima de senhas ou metas criadas durante o uso; se houver incompatibilidade de dados, manter o serviço novo sem tráfego e reconciliar os registros com o backup consistente. O retorno do código não deve desfazer operações válidas dos usuários.

## Limites atuais

- A capacidade real depende da CPU/RAM e do cache da VPS. Os números locais não são compromisso de desempenho em produção.
- `healthy` só comprova que o HTTP do Streamlit responde. `restart: unless-stopped` reinicia um processo encerrado; o Docker não reinicia automaticamente um processo apenas marcado como `unhealthy`.
- Esta imagem não agenda ETL. A rotina de extração atual deve ser revisada separadamente para não executar cargas repetidas ou desnecessárias.
- A configuração compartilhada atual desativa CORS/XSRF. A imagem isolada usa os padrões do Streamlit; validar login e envio de ações pelo túnel antes de liberar, sem copiar aquela desativação automaticamente.
