# Preparação do deploy — quinta-feira, 22/10/2026

## Objetivo e estado

Publicar o Radar revisado na VPS existente, mantendo a conciliação financeira, usuários, metas e carteiras autorizadas. Sem contratação de serviços. A instalação local e a publicação são operações diferentes: a conta/senha criada no notebook não passa automaticamente para `radar.gmlimpeza.net`.

Este documento prepara a execução. Nenhum comando remoto foi executado nesta revisão. O inventário real do servidor é obrigatório antes de fechar os comandos de substituição/reinício: o container conhecido `gm-analytics` também atende as portas 8501 e 8503, além do Radar em 8502.

## Hoje, quarta-feira, 21/10

1. Instalar a revisão r2 no notebook e testar somente em `http://localhost:8504`.
2. Conferir a Base indicada no login e na Gestão; criar/redefinir sempre na mesma instalação do teste.
3. Usar Equipe do Radar para incluir todos os nomes disponíveis e retirar apenas quem a gestão decidir. A seleção anterior é preservada até essa decisão.
4. Conferir uma conta de gestão, uma de supervisão e uma de vendedora: senha provisória, escolha da pessoal, logout, novo login, atualização da página, carteira permitida e PDF.
5. Commitar o código efetivamente validado, incluindo os arquivos SQLite de código entregues anteriormente. Usar `git status --short` e revisar os nomes staged; não enviar `.env`, bancos, caches ou backups ao Git.
6. Obter o inventário de leitura da VPS descrito abaixo. Não executar ETL para realizar esses testes.

## Inventário da VPS, sem alterações

Copiar `inspecionar_vps_radar.sh` deste diretório para o servidor. No terminal da VPS, executar:

```bash
bash /CAMINHO/inspecionar_vps_radar.sh gm-analytics
```

O script imprime imagem atual, portas, volumes, amostra de CPU/memória, caminhos/hashes do código, versões das bibliotecas, metadados dos caches, contagem/integridade do SQLite se existir e horários do ETL no crontab do container. Não imprime variáveis de ambiente com credenciais, hashes de senha nem conteúdo de clientes. Não consulta o Cronos, inicia ETL, reinicia ou publica nada.

Conferir especialmente:

- Se `/opt/gm-analytics` no host e o código dentro do container são iguais ou divergentes.
- Onde estão os volumes persistentes de cache e dados. O SQLite precisa sobreviver à recriação do container; deve ficar em disco local, fora de OneDrive e de compartilhamento de rede.
- Se há autenticação Parquet antiga ou SQLite. A migração deve partir dos usuários da **VPS**, preservando seus hashes e perfis, com backup. Não copiar o SQLite do notebook por cima da base do servidor.
- Como as três aplicações Streamlit são iniciadas e supervisionadas. Preservar 8501 e 8503; não substituir entrypoint ou compose por um modelo presumido.
- Se há rotina de ETL duplicada no host e no container. Comparar também o agendamento do host, sem expor credenciais das linhas de comando. Somente uma extração deve rodar por vez, na janela combinada.

## Homologação na infraestrutura atual

1. Preparar uma pasta/release separada com o commit validado e registrar o commit anterior e a imagem atual.
2. Usar uma porta livre de teste, por exemplo 8514, vinculada a `127.0.0.1`. Não modificar o domínio público para testar uma versão ainda não aprovada.
3. Usar cópia consistente dos dados necessários à homologação. SQLite deve ser copiado pela API de backup, não pela cópia isolada do arquivo enquanto há WAL ativo.
4. Manter usuários de teste, sessões e metas de homologação separados dos de produção. Caches comerciais podem ser copiados para leitura; não apontar gravações do teste para as bases de produção.
5. Não iniciar o cron de ETL no ambiente de homologação e não executar o ETL para fazer o teste de carga.
6. Para processos Streamlit de produção/homologação, desativar o monitoramento de código com `--server.fileWatcherType none`. Atualizações de código entram por reinício controlado. Isso evita o consumo de observadores de arquivos durante vários acessos.

## Resultado local que precisa orientar a homologação

A revisão concluiu 20 logins simultâneos, depois 10 adicionais, e 30 pedidos de PDF, com integridade `ok`, em base fictícia de três clientes. Nesse pico, o percentil 95 foi **38,592 s para entrar** e **21,975 s para baixar o PDF**. O teste confirma as operações; esses tempos **não liberam a aplicação para produção**.

Medir separadamente o tempo do servidor e o tempo percebido no navegador na VPS, com o volume real e as outras aplicações ativas. Como referência inicial, buscar percentil 95 de até 5 s na entrada e 3 s em ações usuais. Se o servidor não sustentar o teste, identificar primeiro reconstruções de payload, releituras dos caches e execuções extras do componente; não reduzir a validação de permissões nem a proteção das senhas para ganhar tempo.

## Critérios antes de liberar

| Área | Conferência necessária |
|---|---|
| Acessos | Criar, redefinir, trocar a provisória, sair, entrar e recarregar; conta desativada e sessão revogada recusadas |
| Permissões | Vendedora vê somente sua carteira; supervisor somente sua equipe; ações administrativas recusadas no servidor para outros perfis |
| Equipe | Todos os nomes presentes no cache disponíveis; excluir e reincluir funcionam; seleção é compartilhada e não apaga histórico |
| Financeiro | Mesmos valores e quatro casas na conferência do Cronos; consolidado integral preservado |
| Concorrência | 20 contas distintas simultâneas, depois margem para 30; não usar a mesma conta em todas as sessões |
| Metas | Conflitos da mesma versão são informados; nenhuma gravação é perdida silenciosamente |
| Caches | Atualização íntegra de carteira/histórico, mesmo snapshot, indisponibilidade do ERP com leitura local e aviso de data |
| Recuperação | Reinício mantém dados; backup restaura numa base separada com integridade `ok`; rollback do código ensaiado |
| Recursos | Medir CPU, memória, tempos de login/ação e erros antes/durante/depois na própria VPS |

Um teste sintético local não garante o desempenho com o volume real de clientes nem a capacidade da VPS. A decisão de liberação usa as medidas do servidor e o comportamento dos três sistemas compartilhados.

## Publicação e retorno

Depois da homologação, definir uma janela curta, gerar backup consistente dos dados e trocar para o commit/release aprovado. O comando exato de reinício depende do inventário do entrypoint/volumes. Conferir o Radar pelo domínio e garantir que sistemas/gestão continuem respondendo.

Se houver erro de acesso, falha de permissão, divergência financeira, perda de dados ou consumo que comprometa as outras aplicações, retornar ao código/imagem anterior. Preservar os usuários e alterações de senha posteriores à atualização; não restaurar Parquets antigos por cima de senhas novas sem migração compatível.

Contas novas do notebook devem ser conferidas individualmente na VPS. Códigos já existentes não devem ter suas senhas sobrescritas automaticamente. A Gestão poderá recuperar esses acessos no próprio ambiente publicado.
