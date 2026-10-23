/* Executável com Node; não consulta o ERP e não exige dependências JS. */
const assert=require('node:assert/strict');
const R=require('../dashboards/radar_component/contrato.js');
const raw={usuario:{cod:'G',nome:'Gestão',role:'gestao'},competencia:'2026-10',mesesMetas:['2026-10','2026-11'],
  vendedoras:[{CodVendedor:'02',Nome:'Bia',IdEquipe:'S2',Supervisor:'Beta',PodeMeta:true},{CodVendedor:'01',Nome:'Ána',IdEquipe:'S1',Supervisor:'Alfa',PodeMeta:true}],
  clientes:[{CodCliFor:'C1',Cliente:'Cliente A',CodVendedorCarteira:'01',VendedorCarteira:'Ana',CurvaABC:'A',
    ComprouNoMes:true,Status:'ATIVO',FatMesAtual:0,MediaMensal:100,ReceitaEmRisco:0,UltimaCompra:'22/10/2026',DiasUltimaCompra:0,MesesUltimaCompra:0,Celular:'5583999990101',
    Historico:[{mes:'2026-10',valor:-100}],ProdutosHabituais:[{Produto:'Item & teste'}]},
    {CodCliFor:'C2',Cliente:'Cliente B',CodVendedorCarteira:'02',CurvaABC:'B',ComprouNoMes:false,Status:'PERDIDO',FatMesAtual:-50,MediaMensal:20,UltimaCompra:'01/06/2026',DiasUltimaCompra:143,MesesUltimaCompra:4}],
  cadastrosMes:[],resumos:{'01':{somaRealizado:0,somaMeta:1000,todasTemMeta:true,percentualMeta:0},
    '02':{somaRealizado:100,somaMeta:null,todasTemMeta:false},'01|02':{somaRealizado:100,somaMeta:null,somaMetaParcial:1000,todasTemMeta:false}},
  financeiro:{'1|01|2026-10':{MetaValor:1000,Versao:7,RealizadoMeta:0},'1|01|2026-11':{Versao:2,MetaValor:1200}},
  cadastroCompletoPorVendedor:{'01':true,'02':false},documentosDisponiveis:{orcamentos:true,prevendas:false},
  orcamentos:[{CodVendedor:'01',CodCliFor:'C1',NumMov:'OR1',ValorLiquido:10}],equipe:{versao:4},
  acessos:{contas:[{codigo:'01',versao:3}]}};
const p=R.adaptar(raw),s={selectedTeamSupervisor:'TODOS',selectedVendedoraCodigo:'TODAS'};
assert.equal(p.usuario.perfil,'gestao');assert.deepEqual(p.vendedores_equipe.map(v=>v.codigo),['01','02']);
assert.equal(p.clientes[0].compra_mes,0);assert.equal(p.clientes[0].comprou_mes,true);
assert.equal(p.clientes[1].compra_mes,-50);assert.equal(p.clientes[1].retomar_contato,true);
assert.equal(p.clientes[0].whatsapp,'5583999990101');assert.equal(R.codigoWhatsApp('8333331111'),'');
assert.equal(R.escopo(p,s).curvas_abc[0].compraram,1);assert.equal(R.escopo(p,s).resumo.somaMeta,null);
assert.equal(R.escopo(p,s).cadastroCompleto,false);
s.selectedTeamSupervisor='S1';const e=R.escopo(p,s);
assert.equal(e.clientes.length,1);assert.equal(e.resumo.somaRealizado,0);assert.equal(e.cadastroCompleto,true);
const id='acao_teste_1234567890123456';
assert.deepEqual(R.evento('pdf_pendentes',{curva:'A'},p,s,id).vendedores,['01']);
assert.deepEqual(R.evento('salvar_meta',{codigo_vendedor:'01',valor_meta:'12.000,55'},p,s,id),{tipo:'salvar_meta',id,vendedor:'01',competencia:'2026-10',valor:'12.000,55',versao:7});
s.metaCompetencia='2026-11';assert.equal(R.evento('salvar_meta',{codigo_vendedor:'01',valor_meta:'100,00'},p,s,id).versao,2);
assert.equal(R.evento('gerir_equipe',{acao:'reincluir',codigo_vendedor:'02'},p,s,id).versao,4);
assert.equal(R.evento('gerir_equipe',{acao:'reincluir',codigo_vendedor:'02'},p,s,id).acao,'incluir');
assert.throws(()=>R.evento('qualquer',{},p,s,id));assert.throws(()=>R.evento('sair_radar',{},p,s,'curto'));
assert.equal(R.num(null),null);assert.equal(R.num(-50),-50);assert.equal(R.num(NaN),null);
assert.equal(R.moedaExata('123456789012.3456'),'R$ 123.456.789.012,3456');
assert.equal(R.moedaExata('-0.0001'),'- R$ 0,0001');
assert.equal(R.situacao({comprou_mes:false,compra_mes:-10,media_mensal:100}),'nao_comprou');
assert.equal(R.situacao({comprou_mes:true,compra_mes:100,media_mensal:100.004}),'na_media');
assert.equal(R.situacao({comprou_mes:true,compra_mes:102,media_mensal:100}),'acima_media');
assert.equal(R.normalizar('Lúcia'),'lucia');
console.log('Contrato Canvas: verificações de campos, escopo, valores nulos/negativos, códigos e versões aprovadas.');
