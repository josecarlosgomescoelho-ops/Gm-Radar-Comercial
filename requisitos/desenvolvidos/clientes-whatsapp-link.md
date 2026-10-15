# Clientes — WhatsApp com Link Direto e Remoção do Telefone Fixo

**Status**: `a-desenvolver`
**Criado em**: 2026-05-09
**Prioridade**: Must Have
**Esforço estimado**: Pequeno (<2h)

---

## Dor de Negócio

O radar e as listagens de clientes exibem o telefone fixo (`FoneCliFor`), que raramente é usado. O número de celular/WhatsApp existe no cadastro (`CelCliFor`) mas não gera um link clicável para iniciar a conversa, obrigando a copiar manualmente o número e abrir o WhatsApp.

## História de Usuário

> Como vendedora, quero clicar direto no número do cliente para abrir o WhatsApp, para que eu inicie o contato sem precisar copiar o número manualmente.

## Critérios de Aceite

- [ ] Remover a exibição de `FoneCliFor` (telefone fixo) em todos os locais do app onde aparece
- [ ] Exibir `CelCliFor` como número de WhatsApp com link `https://wa.me/55XXXXXXXXXXX` (formato internacional, sem espaços ou caracteres especiais)
- [ ] O link deve abrir em nova aba (`target="_blank"`) com ícone do WhatsApp (emoji 📱 ou ícone SVG inline)
- [ ] Se `CelCliFor` estiver vazio, exibir "—" (sem link)
- [ ] A formatação do número deve remover parênteses, traços e espaços antes de montar o link
- [ ] Implementar nos dois apps: `app.py` (aba Clientes, tabela de busca) e `radar_vendedor.py` (card do cliente)

## Dados necessários

- Tabelas: `Cli_For`
- Colunas: `CelCliFor` (usado como WhatsApp), `FoneCliFor` (a remover)
- Status: ✅ Disponível — `CelCliFor` já existe no Cronos

## Impacto na arquitetura atual

- Modificado: `scripts/etl_cache.py` — incluir `CelCliFor` no Parquet de clientes (verificar se já está)
- Modificado: `dashboards/app.py` — substituir coluna telefone por link WhatsApp em tab6
- Modificado: `dashboards/radar_vendedor.py` — atualizar card do cliente com link WhatsApp

## Notas

O formato correto para `wa.me` é: `https://wa.me/55` + DDD + número sem formatação. Exemplo: `(41) 99999-8888` → `https://wa.me/5541999998888`. Aplicar `re.sub(r'\D', '', cel)` para limpar o número.
