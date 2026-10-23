/* Administração local; o Python revalida a sessão, a equipe e a versão de cada gravação. */
window.RadarAcessos={
  render(p) {
    if(p.usuario.perfil!=='gestao') return '';
    const a=p.raw.acessos||{}, q=STATE.acessosSearch.trim().toLocaleLowerCase('pt-BR');
    const contas=(a.contas||[]).filter(c=>!q||`${c.codigo} ${c.nome} ${c.perfil}`.toLocaleLowerCase('pt-BR').includes(q));
    const modo=STATE.accessEditor?.modo||'criar', codigo=STATE.accessEditor?.codigo||'';
    const conta=(a.contas||[]).find(c=>c.codigo===codigo);
    const editing=modo!=='criar', reset=modo==='redefinir', bloqueado=!!STATE.pendingAction;
    const labels={vendedor:'Vendedora',supervisor:'Supervisão',gestao:'Gestão',dev:'Administração técnica'};
    const perfil=STATE.accessCreatePerfil||'vendedor';
    const catalogo=(a.catalogo||[]).filter(c=>c.perfil===perfil&&!(a.contas||[]).some(x=>x.codigo===c.codigo));
    return `<div class="admin-grid">
      <section class="surface-card" aria-label="Contas de acesso">
        <div class="card-header-row"><div><span class="section-title">Perfis e acessos</span><p class="hint">Contas desta instalação. Crie um acesso ou redefina uma senha esquecida.</p></div>
          <button type="button" class="btn btn-xs" data-trigger="reler_acessos" ${bloqueado?'disabled':''}>↻ Atualizar lista</button></div>
        ${a.erro?`<div class="status-banner error">${escapeHtml(a.erro)}</div>`:''}
        <label class="sr-only" for="inputAcessosSearch">Buscar acesso</label>
        <input type="search" id="inputAcessosSearch" class="input-search" placeholder="Buscar nome, código ou perfil" value="${escapeHtml(STATE.acessosSearch)}">
        <div class="data-table-wrapper"><table class="clean-table"><thead><tr><th>Nome e login</th><th>Perfil</th><th>Situação</th><th>Última entrada</th><th>Ações</th></tr></thead><tbody>
        ${contas.map(c=>`<tr data-account-code="${escapeHtml(c.codigo)}"><td><strong>${escapeHtml(c.nome)}</strong><br><code>${escapeHtml(c.codigo)}</code></td>
          <td>${escapeHtml(labels[c.perfil]||c.perfil)}</td><td>${c.ativo?'Ativa':'Desativada'}${c.primeiro||c.troca?'<br><small>Troca de senha pendente</small>':''}</td>
          <td>${escapeHtml(c.ultimoLogin||'Ainda não entrou')}</td><td><div class="row-actions">
          <button type="button" class="btn btn-xs" data-account-edit="${escapeHtml(c.codigo)}" ${bloqueado||!c.editavel?'disabled':''}>Editar perfil</button>
          <button type="button" class="btn btn-xs" data-account-reset="${escapeHtml(c.codigo)}" ${bloqueado||!c.editavel||c.codigo===p.usuario.codigo_vendedor?'disabled':''}>Redefinir senha</button>
          </div></td></tr>`).join('')||'<tr><td colspan="5">Nenhuma conta encontrada.</td></tr>'}</tbody></table></div>
      </section>
      <section class="surface-card" aria-label="Administrar conta"><div class="card-header-row"><span class="section-title">${reset?'Redefinir senha':editing?'Editar perfil e situação':'Criar conta'}</span>
      ${editing?'<button type="button" class="btn btn-xs" id="btnNovaConta">Nova conta</button>':''}</div>
      <form id="formAcesso" class="admin-form" data-draft-scope="acesso_${escapeHtml(modo)}_${escapeHtml(codigo)}_${escapeHtml(perfil)}">
      ${editing?`<p><strong>${escapeHtml(conta?.nome||'Conta não encontrada')}</strong><br>Login: <code>${escapeHtml(codigo)}</code></p>`:`
        <div class="filter-field"><label for="novoAcessoPerfil">Perfil de acesso</label><select id="novoAcessoPerfil" class="select-filter" required>
          ${['vendedor','supervisor','gestao'].map(r=>`<option value="${r}" ${perfil===r?'selected':''}>${labels[r]}</option>`).join('')}</select></div>
        ${perfil==='gestao'?`<div class="filter-field"><label for="novoAcessoCodigo">Login da gestão</label><input id="novoAcessoCodigo" class="input-search" maxlength="64" required autocomplete="off"></div>
          <div class="filter-field"><label for="novoAcessoNome">Nome completo</label><input id="novoAcessoNome" class="input-search" maxlength="256" required></div>`:
          `<div class="filter-field"><label for="novoAcessoCodigo">Pessoa cadastrada no Cronos</label><select id="novoAcessoCodigo" class="select-filter" required><option value="">Selecione um nome</option>
           ${catalogo.map(c=>`<option value="${escapeHtml(c.codigo)}">${escapeHtml(c.nome)} (${escapeHtml(c.codigo)})</option>`).join('')}</select>
           <span class="hint">O login é o código, com os zeros à esquerda. Pessoas com conta já criada aparecem na lista ao lado.</span></div>`}`}
      ${editing&&!reset?`<div class="filter-field"><label for="editarAcessoNome">Nome completo</label><input id="editarAcessoNome" class="input-search" value="${escapeHtml(conta?.nome)}" required maxlength="256"></div>
        <div class="filter-field"><label for="editarAcessoPerfil">Perfil</label><select id="editarAcessoPerfil" class="select-filter">
          ${['vendedor','supervisor','gestao',...(conta?.perfil==='dev'?['dev']:[])].map(r=>`<option value="${r}" ${conta?.perfil===r?'selected':''}>${labels[r]}</option>`).join('')}</select></div>
        <label><input type="checkbox" id="editarAcessoAtivo" ${conta?.ativo?'checked':''}> Conta ativa</label>`:`
        <div class="filter-field"><label for="novoAcessoSenhaProv">Senha provisória</label><div class="row-actions"><input type="password" id="novoAcessoSenhaProv" class="input-search" autocomplete="new-password" minlength="8" required>
        <button type="button" class="btn btn-xs" id="btnToggleTempPass">Mostrar</button></div></div>
        <div class="filter-field"><label for="confirmarAcessoSenha">Confirmar senha provisória</label><input type="password" id="confirmarAcessoSenha" class="input-search" autocomplete="new-password" minlength="8" required></div>
        <p class="hint">A pessoa deverá escolher uma senha pessoal ao entrar. ${reset?'As sessões atuais serão encerradas.':''}</p>`}
      <button type="submit" class="btn btn-primary" ${bloqueado||(editing&&!conta)?'disabled':''}>${reset?'Confirmar redefinição':editing?'Salvar perfil':'Criar acesso'}</button>
      </form><p class="hint">Senhas pessoais não ficam disponíveis para consulta. A senha provisória pode ser vista enquanto você a preenche.</p>
      </section></div>`;
  },
  bind() {
    const show=(modo,codigo)=>{STATE.accessEditor={modo,codigo};STATE.formDrafts={};STATE.skipDraftCapture=true;renderRadar();};
    document.querySelectorAll('[data-account-edit]').forEach(b=>b.onclick=()=>show('atualizar',b.dataset.accountEdit));
    document.querySelectorAll('[data-account-reset]').forEach(b=>b.onclick=()=>show('redefinir',b.dataset.accountReset));
    const nova=document.getElementById('btnNovaConta');if(nova)nova.onclick=()=>show('criar','');
    const perfil=document.getElementById('novoAcessoPerfil');if(perfil)perfil.onchange=()=>{STATE.accessCreatePerfil=perfil.value;STATE.formDrafts={};STATE.skipDraftCapture=true;renderRadar();};
    const busca=document.getElementById('inputAcessosSearch');if(busca)busca.oninput=e=>{STATE.acessosSearch=e.target.value;renderRadar();};
    const toggle=document.getElementById('btnToggleTempPass');if(toggle)toggle.onclick=()=>{const el=document.getElementById('novoAcessoSenhaProv');el.type=el.type==='password'?'text':'password';toggle.textContent=el.type==='password'?'Mostrar':'Ocultar';};
    const form=document.getElementById('formAcesso');if(!form)return;
    form.onsubmit=e=>{
      e.preventDefault();if(STATE.pendingAction)return;
      const a=STATE.payload.raw.acessos, modo=STATE.accessEditor?.modo||'criar';
      const cod=modo==='criar'?document.getElementById('novoAcessoCodigo').value.trim():STATE.accessEditor.codigo;
      const alvo=a.contas.find(c=>c.codigo===cod), dados={acao:modo,codigo:cod};
      if(modo!=='criar')dados.versao=alvo?.versao;
      if(modo==='atualizar') {
        Object.assign(dados,{nome:document.getElementById('editarAcessoNome').value.trim(),perfil:document.getElementById('editarAcessoPerfil').value,ativo:document.getElementById('editarAcessoAtivo').checked});
      } else {
        const senha=document.getElementById('novoAcessoSenhaProv'), confirma=document.getElementById('confirmarAcessoSenha');
        if(senha.value!==confirma.value){confirma.setCustomValidity('As senhas não conferem.');confirma.reportValidity();confirma.oninput=()=>confirma.setCustomValidity('');return;}
        dados.senha=senha.value;
        if(modo==='criar') {
          dados.perfil=document.getElementById('novoAcessoPerfil').value;
          dados.nome=dados.perfil==='gestao'?document.getElementById('novoAcessoNome').value.trim():(a.catalogo.find(c=>c.codigo===cod)?.nome||'');
        }
        senha.value='';confirma.value='';STATE.formDrafts={};
      }
      sendStreamlitEvent('gerir_acesso',dados,modo==='criar'?'Criando conta...':modo==='redefinir'?'Redefinindo senha...':'Salvando perfil...');
    };
  }
};
