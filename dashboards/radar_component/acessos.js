/* Gestao autenticada pelo Python. Nunca recebe hashes ou senhas existentes. */
let contaAcessoSelecionada = '';
let perfilNovoAcesso = 'vendedor';
let buscaAcessos = '';
let eventoAcessoComSenha = null;
let buscaEquipeRadar = '';

function renderizarEquipeRadar() {
  const dados=servidor?.equipe;
  if(!dados || !['gestao','dev'].includes(servidor.usuario.role)) return '';
  const pessoas=dados.pessoas.filter(p=>normalizarTextoBusca(p.nome+' '+p.codigo+' '+p.supervisor).includes(normalizarTextoBusca(buscaEquipeRadar)));
  return `<section class="abc-section" aria-label="Equipe do Radar"><div class="abc-header"><div><h2>Equipe do Radar</h2><p>Todos os nomes disponíveis na base local. Você decide quem participa.</p></div>
    <button type="button" class="btn-secondary-outline" data-equipe="todos" ${pending?'disabled':''}>Incluir todos os nomes</button></div>
    <p class="server-info">Excluir do Radar retira a pessoa das carteiras e metas da equipe. A seleção pode ser revertida por Reincluir. Para bloquear o login, desative o acesso em Perfis e acessos.</p>
    <label for="buscaEquipeRadar">Buscar pessoa, código ou supervisor</label><input class="filter-input" type="search" id="buscaEquipeRadar" value="${escaparHtml(buscaEquipeRadar)}">
    <div class="table-container"><table class="data-table" id="tabelaEquipeRadar"><thead><tr><th>Nome</th><th>Código</th><th>Supervisor</th><th>Situação no cadastro</th><th>No Radar</th><th>Ação</th></tr></thead><tbody>
    ${pessoas.map(p=>`<tr><td>${escaparHtml(p.nome)}</td><td>${escaparHtml(p.codigo)}</td><td>${escaparHtml(p.supervisor||'Sem supervisor')}</td><td>${p.inativo==='S'?'Inativo no cadastro':p.inativo==='N'?'Ativo no cadastro':'Não informada na base'}</td><td>${p.incluida?'Incluída':'Excluída'}</td><td><button type="button" class="btn-secondary-outline" data-equipe="${p.incluida?'excluir':'incluir'}" data-codigo="${escaparHtml(p.codigo)}" ${pending?'disabled':''}>${p.incluida?'Excluir do Radar':'Reincluir'}</button></td></tr>`).join('')||'<tr><td colspan="6">Nenhum nome encontrado na base local.</td></tr>'}
    </tbody></table></div></section>`;
}

function confirmarRecebimentoAcesso(feedback) {
  if(eventoAcessoComSenha && feedback?.evento===eventoAcessoComSenha) {
    const referencia=eventoAcessoComSenha;eventoAcessoComSenha=null;
    // Substitui o valor do componente por um recibo sem senha. O Python ignora esse recibo.
    enviar({tipo:'confirmar_acesso',id:gerarIdAcao(),referencia});
  }
}

function rotuloPerfil(perfil) {
  return ({vendedor:'Vendedora',vendedora:'Vendedora',supervisor:'Supervisão',supervisao:'Supervisão',gestao:'Gestão',dev:'Administração técnica'})[perfil] || perfil;
}

function opcoesPerfil(valor, incluirDev=false) {
  return [...(incluirDev?['dev']:[]),'gestao','supervisor','vendedor'].map(p=>
    `<option value="${p}" ${valor===p?'selected':''}>${escaparHtml(rotuloPerfil(p))}</option>`).join('');
}

function canonicoPerfil(valor) {
  return valor==='vendedora'?'vendedor':valor==='supervisao'?'supervisor':valor;
}

function retornoAcesso(acao,codigo='') {
  const r=state.avisoSupervisor;
  if(!r || r.acao!==acao || (codigo && r.codigo!==codigo)) return '';
  return `<div class="feedback-toast ${r.tipo==='err'?'err':'ok'}" role="status">${escaparHtml(r.texto)}</div>`;
}

function camposSenha(prefixo) {
  return `<div class="filters-advanced-grid">
    <div class="filter-group"><label for="${prefixo}Senha">Senha provisória</label>
      <input class="filter-input" id="${prefixo}Senha" name="senha" type="password" minlength="8" maxlength="72" autocomplete="new-password" required ${pending?'disabled':''}></div>
    <div class="filter-group"><label for="${prefixo}Confirmar">Repita a senha provisória</label>
      <input class="filter-input" id="${prefixo}Confirmar" name="confirmar" type="password" minlength="8" maxlength="72" autocomplete="new-password" required ${pending?'disabled':''}></div>
    </div><label class="server-info"><input type="checkbox" data-mostrar-senha="${prefixo}"> Mostrar a senha provisória enquanto preenche</label>`;
}

function renderizarAreaAcessos() {
  const acesso=servidor?.acessos;
  if(!acesso || !['dev','gestao'].includes(servidor.usuario.role)) return '';
  if(acesso.erro) return `<section class="abc-section"><h2>Perfis e acessos</h2><p role="alert">${escaparHtml(acesso.erro)}</p></section>`;
  const contas=[...acesso.contas].sort((a,b)=>compararNomes(a,b,'nome','codigo'));
  const filtradas=contas.filter(c=>normalizarTextoBusca(c.nome+' '+c.codigo+' '+rotuloPerfil(c.perfil)).includes(normalizarTextoBusca(buscaAcessos)));
  if(!contas.some(c=>c.codigo===contaAcessoSelecionada)) contaAcessoSelecionada=contas[0]?.codigo||'';
  const conta=contas.find(c=>c.codigo===contaAcessoSelecionada);
  const propria=conta?.codigo===servidor.usuario.cod;
  const opcoes=acesso.catalogo.filter(r=>r.perfil===perfilNovoAcesso).sort((a,b)=>compararNomes(a,b,'nome','codigo'));
  return `<section class="abc-section" aria-label="Perfis e acessos">
    <div class="abc-header"><div><h2>Perfis e acessos</h2><p>Crie contas individuais e recupere acessos esquecidos.</p></div>
      <button type="button" class="btn-secondary-outline" data-action="reler-acessos" ${pending?'disabled':''}>Atualizar lista</button></div>
    <p class="server-info">A senha pessoal não fica disponível para leitura. Defina uma provisória quando necessário; a pessoa escolherá a própria senha ao entrar. Gestão pode ver todas as equipes e administrar acessos.</p>
    <div class="filter-group"><label for="buscaAcessos">Buscar conta por nome ou login</label><input class="filter-input" type="search" id="buscaAcessos" value="${escaparHtml(buscaAcessos)}" autocomplete="off"></div>
    <div class="table-container"><table class="data-table" id="tabelaAcessos"><thead><tr><th>Nome</th><th>Login</th><th>Perfil</th><th>Acesso</th><th>Último login</th><th>Senha</th></tr></thead>
      <tbody>${filtradas.map(c=>`<tr><td>${escaparHtml(c.nome)}</td><td>${escaparHtml(c.codigo)}</td><td>${escaparHtml(rotuloPerfil(c.perfil))}</td><td>${c.ativo?'Ativo':'Desativado'}</td><td>${escaparHtml(c.ultimoLogin||'Ainda não entrou')}</td><td>${c.primeiro||c.troca?'Troca obrigatória':'Pessoal definida'}</td></tr>`).join('')||'<tr><td colspan="6">Nenhuma conta encontrada.</td></tr>'}</tbody></table></div>
  </section>
  <section class="abc-section" aria-label="Criar acesso"><h2>Criar acesso</h2>
    <form data-acesso="criar" autocomplete="off"><div class="filters-advanced-grid">
      <div class="filter-group"><label for="perfilNovoAcesso">Perfil da nova conta</label><select class="filter-select" id="perfilNovoAcesso" name="perfil" ${pending?'disabled':''}>${opcoesPerfil(perfilNovoAcesso)}</select></div>
      ${perfilNovoAcesso==='gestao'?`
        <div class="filter-group"><label for="codigoNovoAcesso">Login da coordenação</label><input class="filter-input" id="codigoNovoAcesso" name="codigo" maxlength="64" required autocomplete="off"></div>
        <div class="filter-group"><label for="nomeNovoAcesso">Nome da pessoa</label><input class="filter-input" id="nomeNovoAcesso" name="nome" maxlength="256" required autocomplete="off"></div>`:`
        <div class="filter-group"><label for="codigoNovoAcesso">Responsável na equipe atual</label><select class="filter-select" id="codigoNovoAcesso" name="codigo" required>
          <option value="">Selecione pelo nome</option>${opcoes.map(r=>`<option value="${escaparHtml(r.codigo)}">${escaparHtml(r.nome)} (${escaparHtml(r.codigo)})${r.supervisor?' • '+escaparHtml(r.supervisor):''}</option>`).join('')}</select></div>`}
    </div>${perfilNovoAcesso!=='gestao' && !opcoes.length?'<p class="server-notice">Não há responsável elegível para este perfil na equipe local selecionada. Confira a equipe na barra lateral.</p>':''}
    ${camposSenha('criarAcesso')}<button class="btn-primary-navy" type="submit" ${pending?'disabled':''}>Criar conta com troca obrigatória</button>${retornoAcesso('criar')}</form>
  </section>
  <section class="abc-section" aria-label="Administrar conta"><h2>Administrar conta existente</h2>
    ${!conta?'<p>Nenhuma conta cadastrada.</p>':`
      <div class="filter-group"><label for="selectContaAcesso">Pessoa</label><select class="filter-select" id="selectContaAcesso" ${pending?'disabled':''}>
        ${contas.map(c=>`<option value="${escaparHtml(c.codigo)}" ${c.codigo===conta.codigo?'selected':''}>${escaparHtml(c.nome)} (${escaparHtml(c.codigo)})</option>`).join('')}</select></div>
      ${!conta.editavel?'<p class="server-info">Este acesso é administrado pelo responsável técnico.</p>':`
      <form data-acesso="atualizar" data-codigo="${escaparHtml(conta.codigo)}" data-versao="${conta.versao}">
        <div class="filters-advanced-grid"><div class="filter-group"><label for="nomeContaAcesso">Nome</label><input class="filter-input" id="nomeContaAcesso" name="nome" value="${escaparHtml(conta.nome)}" maxlength="256" required></div>
          <div class="filter-group"><label for="perfilContaAcesso">Perfil</label><select class="filter-select" id="perfilContaAcesso" name="perfil" ${propria?'disabled':''}>${opcoesPerfil(canonicoPerfil(conta.perfil),conta.perfil==='dev')}</select></div></div>
        <label class="server-info"><input type="checkbox" name="ativo" ${conta.ativo?'checked':''} ${propria?'disabled':''}> Acesso ativo</label>
        <p class="server-info">Alterar o perfil ou desativar o acesso encerra as sessões da pessoa. Seu próprio perfil de gestão fica protegido nesta tela.</p>
        <button type="submit" class="btn-primary-navy" ${pending?'disabled':''}>Salvar perfil e situação</button>${retornoAcesso('atualizar',conta.codigo)}
      </form>
      ${propria?'<p class="server-info">Outro coordenador pode redefinir sua senha, se necessário.</p>':`
        <hr><h3>Redefinir senha esquecida</h3><p class="server-info">Login: <strong>${escaparHtml(conta.codigo)}</strong>. As outras contas não serão alteradas.</p>
        <form data-acesso="redefinir" data-codigo="${escaparHtml(conta.codigo)}" data-versao="${conta.versao}" autocomplete="off">
        ${camposSenha('redefinirAcesso')}<button type="submit" class="btn-primary-navy" ${pending?'disabled':''}>Definir senha provisória</button>${retornoAcesso('redefinir',conta.codigo)}</form>`}`}`}
  </section>`;
}

document.getElementById('mainContent').addEventListener('change',e=>{
  if(e.target.id==='perfilNovoAcesso') {perfilNovoAcesso=e.target.value;renderizarAplicacao();}
  if(e.target.id==='selectContaAcesso') {
    contaAcessoSelecionada=e.target.value;pending=true;
    state.avisoSupervisor={tipo:'ok',texto:'Conferindo a situação atual desta conta…'};
    enviar({tipo:'reler_acessos',id:gerarIdAcao()});renderizarAplicacao();
  }
  const prefixo=e.target.getAttribute('data-mostrar-senha');
  if(prefixo) for(const suffix of ['Senha','Confirmar']) document.getElementById(prefixo+suffix).type=e.target.checked?'text':'password';
});
let buscaAcessoTimer;
document.getElementById('mainContent').addEventListener('input',e=>{
  if(e.target.id==='buscaEquipeRadar') {
    buscaEquipeRadar=e.target.value;const pos=e.target.selectionStart;
    clearTimeout(buscaAcessoTimer);buscaAcessoTimer=setTimeout(()=>{
      renderizarAplicacao();const input=document.getElementById('buscaEquipeRadar');
      if(input) {input.focus();input.setSelectionRange(pos,pos);}
    },220);return;
  }
  if(e.target.id!=='buscaAcessos') return;
  buscaAcessos=e.target.value;const pos=e.target.selectionStart;
  clearTimeout(buscaAcessoTimer);buscaAcessoTimer=setTimeout(()=>{
    renderizarAplicacao();const input=document.getElementById('buscaAcessos');
    if(input) {input.focus();input.setSelectionRange(pos,pos);}
  },220);
});
document.getElementById('mainContent').addEventListener('click',e=>{
  const equipe=e.target.closest('[data-equipe]');
  if(equipe && !pending && servidor?.equipe) {
    pending=true;state.avisoSupervisor={tipo:'ok',texto:'Salvando participação na equipe…'};
    enviar({tipo:'gerir_equipe',id:gerarIdAcao(),acao:equipe.dataset.equipe,codigo:equipe.dataset.codigo||'',versao:servidor.equipe.versao});
    renderizarAplicacao();return;
  }
  if(e.target.closest('[data-action="reler-acessos"]') && !pending) {
    pending=true;enviar({tipo:'reler_acessos',id:gerarIdAcao()});renderizarAplicacao();
  }
});
document.getElementById('mainContent').addEventListener('submit',e=>{
  const form=e.target.closest('form[data-acesso]');if(!form) return;
  e.preventDefault();
  if(pending || !servidor?.acessos || !['dev','gestao'].includes(servidor.usuario.role)) return;
  const acao=form.getAttribute('data-acesso');
  const evento={tipo:'gerir_acesso',id:gerarIdAcao(),acao};
  if(acao==='criar') {
    evento.perfil=form.querySelector('[name="perfil"]').value;
    evento.codigo=form.querySelector('[name="codigo"]').value.trim();
    evento.nome=evento.perfil==='gestao'?form.querySelector('[name="nome"]').value.trim():
      (servidor.acessos.catalogo.find(r=>r.codigo===evento.codigo)?.nome||'');
  } else {
    evento.codigo=form.getAttribute('data-codigo');evento.versao=Number(form.getAttribute('data-versao'));
  }
  if(acao==='atualizar') {
    evento.nome=form.querySelector('[name="nome"]').value.trim();
    evento.perfil=form.querySelector('[name="perfil"]').value;
    evento.ativo=form.querySelector('[name="ativo"]').checked;
  } else {
    const senha=form.querySelector('[name="senha"]'),confirmar=form.querySelector('[name="confirmar"]');
    if(senha.value!==confirmar.value || senha.value.length<8 || new TextEncoder().encode(senha.value).length>72) {
      state.avisoSupervisor={tipo:'err',texto:'Confirme a mesma senha com ao menos 8 caracteres e até 72 bytes.'};
      renderizarAplicacao();return;
    }
    evento.senha=senha.value;senha.value='';confirmar.value='';
    eventoAcessoComSenha=evento.id;
  }
  pending=true;state.avisoSupervisor={tipo:'ok',texto:'Salvando acesso…',acao,codigo:evento.codigo};
  enviar(evento);renderizarAplicacao();
});
