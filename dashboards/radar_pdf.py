"""PDF de pendências gerado em memória a partir da carteira autorizada."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle
from radar_metas import autorizados


def selecionar_pendentes(payload, usuario, responsaveis, evento):
    curva = evento.get('curva')
    if curva not in {'A', 'B', 'C', 'TODAS'}:
        raise ValueError('Curva inválida para o PDF.')
    if (payload['usuario']['cod'], payload['usuario']['role']) != (str(usuario['cod']), str(usuario['role'])):
        raise PermissionError('Atualize a sessão antes de exportar.')
    equipe = autorizados(usuario, responsaveis)
    equipe = equipe.loc[equipe.Tipo.eq('V') & ~equipe.CodVendedor.isin(['00002', '01174'])]
    permitidos = set(equipe.CodVendedor.astype(str))
    codigos = evento.get('vendedores')
    if not isinstance(codigos, list) or not codigos or any(not isinstance(c, str) for c in codigos):
        raise ValueError('Selecione uma vendedora ou equipe para o PDF.')
    if not set(codigos).issubset(permitidos):
        raise PermissionError('O PDF solicitado inclui uma vendedora fora do seu acesso.')
    itens = [c for c in payload['clientes'] if c['CodVendedorCarteira'] in codigos
             and c['CompraNos12Meses'] and not c['ComprouNoMes']
             and (curva == 'TODAS' or c['CurvaABC'] == curva)]
    itens.sort(key=lambda c: (c['CurvaABC'], -c['MediaMensal'], c['Cliente'], c['CodCliFor']))
    nomes = [r.Vendedor for r in equipe.itertuples() if r.CodVendedor in codigos]
    return itens, nomes, curva


def gerar_pdf(payload, clientes, nomes, curva):
    buffer = BytesIO()
    navy = colors.HexColor('#1B3A5C')
    text = ParagraphStyle('texto', fontName='Helvetica', fontSize=8, leading=11, textColor=navy)
    small = ParagraphStyle('pequeno', parent=text, fontSize=7, leading=9)
    title = ParagraphStyle('titulo', parent=text, fontName='Helvetica-Bold', fontSize=17, leading=21, spaceAfter=8)
    head = ParagraphStyle('cabecalho', parent=small, fontName='Helvetica-Bold', textColor=colors.white)
    def p(value, style=text):
        return Paragraph(escape(str(value or '-')), style)
    def moeda(value):
        return 'R$ ' + f'{float(value):,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=12*mm, rightMargin=12*mm,
                            topMargin=13*mm, bottomMargin=15*mm,
                            title='Clientes que faltam comprar - Radar Comercial', author='GM Limpezas')
    story = [p('GM Limpezas | Clientes que faltam comprar', title),
             p('Curvas A, B e C' if curva == 'TODAS' else 'Curva ' + curva),
             p('Vendedora(s): ' + ', '.join(nomes)),
             p('Mês de referência: ' + payload['competencia'] + ' | Dados até: ' + payload['referenciaCarteira']),
             p('Carteira: clientes com compra entre ' + payload['periodoCarteiraInicio'] + ' e ' + payload['referenciaCarteira'] + '. Responsável atual do cadastro.', small),
             p('Pendência: nenhuma compra válida no mês de referência. Devolução isolada não conta como compra. Curva ABC global preservada.', small),
             p('Total de clientes: ' + str(len(clientes))), Spacer(1, 6*mm)]
    titulos = ['Cód. / Curva', 'Cliente', 'Responsável', 'Contato', 'Última compra', 'Dias sem comprar', 'Média mensal (12m)']
    rows = [[p(t, head) for t in titulos]]
    for c in clientes:
        contato = c.get('Celular') or c.get('Telefone') or 'Não informado'
        rows.append([p(c['CodCliFor'] + ' / ' + c['CurvaABC'], small), p(c['Cliente']),
                     p(c['VendedorCarteira'], small), p(contato, small),
                     p(c.get('UltimaCompra') or '-', small), p(str(c['DiasUltimaCompra']), small),
                     p(moeda(c['MediaMensal']), small)])
    if clientes:
        widths = [22, 82, 44, 33, 29, 25, 38]
        table = LongTable(rows, colWidths=[w*mm for w in widths], repeatRows=1, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), navy),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F1F5F9')]),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 6), ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LINEBELOW', (0,0), (-1,0), .5, navy),
            ('LINEBELOW', (0,1), (-1,-1), .2, colors.HexColor('#D9E2EC')),
        ]))
        story.append(table)
    else:
        story.append(p('Nenhum cliente pendente neste recorte.'))
    def rodape(canvas, documento):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(navy)
        canvas.drawString(12*mm, 8*mm, 'Radar Comercial | Dados salvos até ' + payload['referenciaCarteira'])
        canvas.drawRightString(285*mm, 8*mm, 'Página ' + str(documento.page))
        canvas.restoreState()
    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return buffer.getvalue()
