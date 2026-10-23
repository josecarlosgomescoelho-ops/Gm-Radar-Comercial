/* Contrato da interface: recebe somente o recorte autorizado pelo Python. */
(function (root) {
  'use strict';
  const nomes = new Intl.Collator('pt-BR', {sensitivity:'base'});
  const num = v => v == null || v === '' || !Number.isFinite(Number(v)) ? null : Number(v);
  const comparar = (a,b,nome='nome',codigo='codigo') => nomes.compare(String(a[nome]??''),String(b[nome]??'')) ||
    (String(a[codigo]??'') < String(b[codigo]??'') ? -1 : String(a[codigo]??'') > String(b[codigo]??'') ? 1 : 0);
  const ordenar = (xs,nome,codigo) => [...(xs||[])].sort((a,b)=>comparar(a,b,nome,codigo));
  const normalizar = v => String(v??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR');
  function situacao(c) {
    if(!c.comprou_mes)return 'nao_comprou';
    if(c.media_mensal==null||c.media_mensal<=0||c.compra_mes==null)return 'sem_media';
    const compra=Math.round(c.compra_mes*100),media=Math.round(c.media_mensal*100);
    return compra<media?'abaixo_media':compra===media?'na_media':'acima_media';
  }
  function resumo(raw,codigos) {
    const key=[...codigos].sort().join('|');
    // Somente consolidacoes calculadas no servidor: nunca soma margens nem metas parciais.
    return raw.resumos?.[key] || {somaRealizado:null,somaMeta:null,percentualMeta:null,larguraBarra:0,
      rentabilidadeConsolidada:null,todasTemMeta:false,vendedorasSemMeta:[]};
  }
  function codigoWhatsApp(celular) {
    let s=String(celular||'').replace(/\D/g,'');
    if(s.length===11) s='55'+s;
    return /^55\d{2}9\d{8}$/.test(s) ? s : '';
  }
  function moedaExata(valor) {
    if(typeof valor!=='string'||! /^-?\d+\.\d{4}$/.test(valor))return 'Indisponível';
    const negativo=valor.startsWith('-'),[inteiro,fracao]=valor.replace(/^-/,'').split('.');
    return `${negativo?'- ':''}R$ ${inteiro.replace(/\B(?=(\d{3})+(?!\d))/g,'.')},${fracao}`;
  }
  function cliente(c,docs) {
    const status=c.Status, comprou=c.ComprouNoMes===true, fat=num(c.FatMesAtual), media=num(c.MediaMensal);
    const dias=c.UltimaCompra ? num(c.DiasUltimaCompra) : null;
    const meses=num(c.MesesUltimaCompra);
    const prioridade=['CRITICO','ATENCAO','NOVO'].includes(status) ||
      (comprou && fat!=null && media!=null && (fat<media || c.AbaixoMedia)) || (c.CadastradoNoMes && !comprou);
    const retomar=status==='PERDIDO' || (dias!=null && dias>=120);
    let motivo='Compra no mês igual ou acima da média';
    if(c.CadastradoNoMes) motivo=comprou ? 'Cadastrado neste mês • Compra confirmada' : 'Cadastrado neste mês • Sem primeira compra confirmada';
    else if(status==='CRITICO') motivo=`Prioridade alta • ${dias} dias sem comprar`;
    else if(retomar) motivo=dias==null ? 'Retomar contato • Sem compra nos 12 meses' : `Retomar contato • ${dias} dias sem comprar`;
    else if(!comprou) motivo=`Curva ${c.CurvaABC} • Ainda não comprou neste mês`;
    else if(c.AbaixoMedia) motivo='Compra do mês mais de 20% abaixo da média • Mês parcial';
    else if(fat<media) motivo='Compra do mês abaixo da média • Mês parcial';
    return {codigo:String(c.CodCliFor),nome:c.Cliente,nome_fantasia:c.RazaoSocial||c.Cliente,
      vendedora_codigo:String(c.CodVendedorCarteira),vendedora_nome:c.VendedorCarteira,curva:c.CurvaABC,
      status,compra_mes:fat,comprou_mes:comprou,media_mensal:media,abaixo_20:c.AbaixoMedia===true,
      ultima_compra_data:c.UltimaCompra,ultima_compra_valor:num(c.ValorUltimaCompra),dias_sem_comprar:dias,
      periodo_ultima:meses==null?'sem_12m':meses===0?'neste_mes':meses===1?'mes_anterior':meses<=4?'entre_2_4m':'mais_4m',
      comprou_ultimos_2m_calendario:c.AtivoUltimos2Meses===true,ja_comprou_primeira_vez:!!c.PrimeiraCompraData,
      data_cadastro:c.DataCadastro,primeira_compra_data:c.PrimeiraCompraData,telefone:c.Telefone||c.Celular||'',
      whatsapp:codigoWhatsApp(c.Celular),contato_nome:'',rentabilidade:num(c.RentPerc),
      historico_12m:c.Historico||[],produtos_habituais:(c.ProdutosHabituais||[]).map(x=>x.Produto),
      documentos_abertos:docs.get(String(c.CodCliFor))||[],prioridade_comercial:prioridade,retomar_contato:retomar,
      prioridade_nivel:status==='CRITICO'||c.AbaixoMedia?'alta':prioridade?'media':'normal',
      ordem_status:({CRITICO:1,ATENCAO:2,NOVO:3,ATIVO:4,PERDIDO:5})[status]??99,
      receita_risco:num(c.ReceitaEmRisco)||0,motivo_comercial:motivo};
  }
  function adaptar(raw) {
    if(!raw || !raw.usuario || !Array.isArray(raw.vendedoras) || !Array.isArray(raw.clientes)) throw Error('Base da interface inválida.');
    const role=String(raw.usuario.role||'').toLowerCase();
    const perfil=['dev','gestao'].includes(role)?'gestao':['supervisor','supervisao'].includes(role)?'supervisao':
      ['vendedor','vendedora'].includes(role)?'vendedora':null;
    if(!perfil) throw Error('Perfil da interface inválido.');
    const nomesV=new Map(raw.vendedoras.map(v=>[String(v.CodVendedor),v.Nome]));
    function documento(d,tipo) {return {numero:String(d.NumMov),data:d.DtMov,cliente_codigo:String(d.CodCliFor),
      cliente_nome:d.Cliente||d.NomeCliFor,vendedora_codigo:String(d.CodVendedor),vendedora:nomesV.get(String(d.CodVendedor))||String(d.CodVendedor),
      valor:num(d.ValorLiquido),situacao:'Em aberto na última atualização',tipo};}
    const orc=(raw.orcamentos||[]).map(d=>documento(d,'Orçamento'));
    const pv=(raw.prevendas||[]).map(d=>documento(d,'Pré-venda'));
    const docs=new Map();
    for(const d of [...orc,...pv]) {if(!docs.has(d.cliente_codigo)) docs.set(d.cliente_codigo,[]);docs.get(d.cliente_codigo).push(d);}
    const cs=raw.clientes.map(c=>cliente(c,docs)), cad=(raw.cadastrosMes||[]).map(c=>cliente(c,docs));
    const vs=raw.vendedoras.map(v=>{
      const cod=String(v.CodVendedor), f=raw.financeiro?.[`1|${cod}|${raw.competencia}`]||{};
      const carteira=cs.filter(c=>c.vendedora_codigo===cod);
      return {codigo:cod,nome:v.Nome,supervisor:v.Supervisor||'Sem supervisor',id_equipe:v.IdEquipe,
        participa_radar:true,pode_meta:v.PodeMeta===true,meta:num(f.MetaValor),realizado:num(f.RealizadoMeta),
        rentabilidade:num(f.RentabilidadePct),clientes_carteira:carteira.length,compraram_mes:carteira.filter(c=>c.comprou_mes).length,
        prioridades:carteira.filter(c=>c.prioridade_comercial).length,cadastros_mes:raw.cadastroCompletoPorVendedor?.[cod]===true ? cad.filter(c=>c.vendedora_codigo===cod).length : null,
        orcamentos_abertos:raw.documentosDisponiveis?.orcamentos===true ? orc.filter(d=>d.vendedora_codigo===cod).length : null,
        prevendas_abertas:raw.documentosDisponiveis?.prevendas===true ? pv.filter(d=>d.vendedora_codigo===cod).length : null};
    });
    return {raw,usuario:{nome:raw.usuario.nome,perfil,codigo_vendedor:String(raw.usuario.cod)},
      clientes:cs,cadastros_mes_lista:cad,vendedores_equipe:ordenar(vs),
      orcamentos_abertos_lista:orc,prevendas_abertas_lista:pv,
      cadastros_fora_carteira:(raw.cadastrosSemCarteiraAtiva||[]).map(c=>({codigo:c.CodCliFor,nome:c.Cliente,
        data_cadastro:c.DataCadastro,responsavel:c.VendedorCarteira||c.CodVendedorCarteira||'Não informado',situacao:c.SituacaoResponsavel})),
      periodo_carteira_12m:`${raw.periodoCarteiraInicio} a ${raw.referenciaCarteira}`,
      atualizado_em:raw.atualizacaoCarteira,mes_referencia:raw.competencia,mes_parcial:true,
      versao:raw.instalacao?.versao,ambiente:raw.instalacao?.ambiente,base_id:raw.instalacao?.base,
      avisos:raw.avisos||[],documentosDisponiveis:raw.documentosDisponiveis||{}};
  }
  function escopo(p,state) {
    let vs=p.vendedores_equipe.filter(v=>state.selectedTeamSupervisor==='TODOS'||v.id_equipe===state.selectedTeamSupervisor);
    if(state.selectedVendedoraCodigo!=='TODAS') vs=vs.filter(v=>v.codigo===state.selectedVendedoraCodigo);
    const ids=vs.map(v=>v.codigo), codigos=new Set(ids);
    const filtro=xs=>(xs||[]).filter(c=>codigos.has(c.vendedora_codigo));
    const clientes=filtro(p.clientes);
    const curvas=['A','B','C'].map((curva,i)=>{const grupo=clientes.filter(c=>c.curva===curva), compraram=grupo.filter(c=>c.comprou_mes).length;
      return {curva,total:grupo.length,compraram,faltam:grupo.length-compraram,percentual:grupo.length?100*compraram/grupo.length:0,proporcao_regra:['20%','30%','50%'][i]};});
    return {...p,vendedores_equipe:vs,clientes,cadastros_mes_lista:filtro(p.cadastros_mes_lista),curvas_abc:curvas,
      orcamentos_abertos_lista:filtro(p.orcamentos_abertos_lista),prevendas_abertas_lista:filtro(p.prevendas_abertas_lista),
      resumo:resumo(p.raw,ids),cadastroCompleto:ids.length>0 && ids.every(c=>p.raw.cadastroCompletoPorVendedor?.[c]===true)};
  }
  function evento(tipo,dados,p,state,id) {
    if(!/^[A-Za-z0-9_-]{16,80}$/.test(id)) throw Error('Identificador inválido.');
    const out={tipo,id};
    if(tipo==='pdf_pendentes') return {...out,curva:dados.curva,vendedores:escopo(p,state).vendedores_equipe.map(v=>v.codigo)};
    if(tipo==='salvar_meta') {const mes=state.metaCompetencia||p.raw.competencia;
      return {...out,vendedor:dados.codigo_vendedor,competencia:mes,valor:String(dados.valor_meta),
        versao:p.raw.financeiro?.[`1|${dados.codigo_vendedor}|${mes}`]?.Versao??0};}
    if(tipo==='gerir_equipe') return {...out,acao:({incluir_todos:'todos',reincluir:'incluir',excluir:'excluir'})[dados.acao],codigo:dados.codigo_vendedor,versao:p.raw.equipe?.versao};
    if(tipo==='gerir_acesso') return {...out,...dados};
    if(!['reler_acessos','reler_arquivos','sair_radar','confirmar_acesso','solicitar_base'].includes(tipo)) throw Error('Ação desconhecida.');
    return out;
  }
  const api={num,comparar,ordenar,normalizar,situacao,adaptar,escopo,resumo,evento,codigoWhatsApp,moedaExata};
  if(typeof module!=='undefined'&&module.exports) module.exports=api;
  root.RadarContrato=api;
})(typeof window!=='undefined'?window:globalThis);
