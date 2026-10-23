/*************************************************************************
     * 1. UTILITÁRIOS DE SEGURANÇA, FORMATAÇÃO E ESCAPE (PROTEÇÃO XSS)
     *************************************************************************/
    function escapeHtml(val) {
      if (val === null || val === undefined) return "";
      return String(val)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function formatCurrency(val, decimals = 2) {
      if (val === null || val === undefined || isNaN(Number(val))) return "Indisponível";
      return Number(val).toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL",
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
      });
    }

    function formatPercent(val, decimals = 1) {
      if (val === null || val === undefined || isNaN(Number(val))) return "Indisponível";
      return Number(val).toLocaleString("pt-BR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
      }) + "%";
    }

    function formatNowSaoPaulo() {
      try {
        return new Intl.DateTimeFormat("pt-BR", {
          timeZone: "America/Sao_Paulo",
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit"
        }).format(new Date());
      } catch (e) {
        return new Date().toLocaleString("pt-BR");
      }
    }

    function generateRequestId(prefix) {
      const bytes=new Uint8Array(16);window.crypto.getRandomValues(bytes);
      return prefix.slice(0,30)+'_'+Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
    }
    

    /*************************************************************************
     * 2. ESTADO GLOBAL PRESERVADO ENTRE RENDERIZAÇÕES E CLIQUES
     *************************************************************************/
    const STATE = {
      pageOpenedAt: formatNowSaoPaulo(),

      // Payload autorizado pelo servidor
      payload: null,

      // Navegação de Supervisão/Gestão ("visao_geral" é sempre a inicial)
      activeRoleTab: "visao_geral",
      selectedTeamSupervisor: "TODOS",
      selectedVendedoraCodigo: "TODAS",
      supervisaoViewMode: "cards", // "cards" | "table"

      // Painéis persistentes da Curva ABC
      showAbcTextTable: false,
      showAbcBaseInfo: false,

      // Recortes e Filtros da Lista de Clientes
      activeRecorte: "prioridades", // "prioridades" (padrão) | "retomar" | "cadastrados_mes" | "todos"
      subFiltroCadastrosMes: "todos", // "todos" | "ja_compraram" | "sem_primeira_compra"
      searchQuery: "",
      filtroCurva: "TODAS", // "TODAS" | "A" | "B" | "C"
      filtroSituacaoMes: "TODAS", // "TODAS" | "nao_comprou" | "abaixo_media" | "mais_20_abaixo" | "na_media" | "acima_media"
      ordenacao: "az", // "az" (padrão) | "prioridade" | "maior_media" | "maior_tempo" | "maior_dif_abaixo"

      // Gaveta "Mais Filtros"
      showMoreFilters: false,
      filtroDoisMesesCal: "TODOS", // "TODOS" | "com_compra_2m" | "sem_compra_2m"
      filtroPeriodoUltima: "TODOS", // "TODOS" | "neste_mes" | "mes_anterior" | "entre_2_4m" | "mais_4m" | "sem_12m"
      filtroDiasSemComprar: "TODOS", // "TODOS" | "ate_30" | "31_60" | "61_120" | "mais_120" | "sem_12m"
      filtroFaixaMedia: "TODAS", // "TODAS" | "ate_1500" | "1500_3500" | "acima_3500"
      filtroValorUltima: "TODOS", // "TODOS" | "ate_1500" | "1500_3500" | "acima_3500"
      filtroDifMedia: "TODAS", // "TODAS" | "mais_2000_abaixo" | "ate_2000_abaixo" | "igual_acima"

      // Paginação e Detalhes Persistentes
      currentPage: 1,
      pageSize: 25,
      expandedClientCodes: new Set(),

      // Busca de Equipe e Acessos (Gestão)
      equipeSearch: "",
      acessosSearch: "",
      tempPasswordVisible: false,

      // Controle de Eventos Assíncronos Pendentes (Impede duplo envio)
      pendingAction: null, // { id, tipo, label, startedAt }
      lastFeedback: null,  // { status: 'success'|'error'|'warning'|'info', message, actionId }
      readyPdfFile: null,  // { nome, base64, escopo }

      // Modal ativo
      activeModal: null // { type: 'whatsapp'|'orcamentos'|'prevendas'|'diagnostico'|'guia'|'login_preview', data: ... }
    };

    /*************************************************************************
     * 3. GERADOR DE DADOS DEMONSTRATIVOS ISOLADOS (SOMENTE MODO CANVAS)
     *************************************************************************/
    

    let lastFrameHeight=0, heightQueued=false, lastRenderSignature='', seenFeedback='', seenPdf='';
    function adjustStreamlitFrameHeight() {
      if(heightQueued)return;heightQueued=true;
      requestAnimationFrame(()=>{
        heightQueued=false;
        const root=document.getElementById('radarAppRoot');
        const height=Math.max(520,Math.ceil(root.getBoundingClientRect().bottom+window.scrollY+16));
        if(height===lastFrameHeight)return;lastFrameHeight=height;
        window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setFrameHeight',height},'*');
      });
    }
    function sendStreamlitEvent(tipo,dados,label='Processando...') {
      if(STATE.pendingAction&&!(['reler_arquivos','reler_acessos','sair_radar'].includes(tipo)&&STATE.pendingAction.timedOut))return;
      const id=generateRequestId(tipo);
      let value;
      try {value=RadarContrato.evento(tipo,dados,STATE.payload,STATE,id);}
      catch(error){STATE.lastFeedback={status:'error',message:error.message};renderRadar();return;}
      STATE.pendingAction={id,tipo,label,startedAt:Date.now()};STATE.lastFeedback=null;
      renderRadar();
      window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setComponentValue',value},'*');
      setTimeout(()=>{
        if(STATE.pendingAction?.id!==id)return;
        STATE.pendingAction.timedOut=true;
        STATE.lastFeedback={status:'warning',message:'A resposta está demorando. Aguarde ou releia os arquivos para conferir o resultado antes de repetir a ação.'};
        renderRadar();
      },30000);
    }
    window.addEventListener('message',event=>{
      if(event.source!==window.parent || event.data?.type!=='streamlit:render')return;
      const args=event.data.args||{};
      const signature=JSON.stringify([args.revisao,args.atualizacoes,args.feedback,args.arquivoPdf?.id]);
      if(!args.payload&&!STATE.payload){
        if(!STATE.solicitouBase){STATE.solicitouBase=true;window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:setComponentValue',value:{tipo:'solicitar_base',id:generateRequestId('base')}},'*');}
        return;
      }
      if(signature===lastRenderSignature)return;
      try {
        if(args.payload) {
          const next=RadarContrato.adaptar(args.payload);
          const changed=STATE.payload && (STATE.payload.usuario.codigo_vendedor!==next.usuario.codigo_vendedor || STATE.payload.usuario.perfil!==next.usuario.perfil);
          if(changed){STATE.formDrafts={};STATE.skipDraftCapture=true;STATE.expandedClientCodes.clear();STATE.activeRoleTab='visao_geral';STATE.selectedTeamSupervisor='TODOS';STATE.selectedVendedoraCodigo='TODAS';STATE.activeModal=null;STATE.readyPdfFile=null;STATE.pendingAction=null;}
          STATE.payload=next;STATE.solicitouBase=false;
          if(!next.vendedores_equipe.some(v=>v.id_equipe===STATE.selectedTeamSupervisor)) STATE.selectedTeamSupervisor='TODOS';
          if(!next.vendedores_equipe.some(v=>v.codigo===STATE.selectedVendedoraCodigo)) STATE.selectedVendedoraCodigo='TODAS';
        }
        if(STATE.payload&&args.atualizacoes)for(const k of ['acessos','equipe','instalacao']){if(Object.hasOwn(args.atualizacoes,k))STATE.payload.raw[k]=args.atualizacoes[k];}
        const pdfSolicitadoAgora=STATE.pendingAction?.tipo==='pdf_pendentes'&&STATE.pendingAction.id===args.arquivoPdf?.id;
        const fb=args.feedback;
        if(fb?.evento && fb.evento!==seenFeedback) {
          seenFeedback=fb.evento;
          if(!STATE.pendingAction || STATE.pendingAction.id===fb.evento) {
            if(STATE.pendingAction?.id===fb.evento)STATE.pendingAction=null;
            STATE.lastFeedback={status:fb.tipo==='ok'?'success':'error',message:fb.texto,actionId:fb.evento};
            if(fb.tipo==='ok'&&['criar','redefinir','atualizar'].includes(fb.acao)) {STATE.accessEditor=null;STATE.formDrafts={};STATE.skipDraftCapture=true;}
          }
        }
        if(args.arquivoPdf?.base64 && args.arquivoPdf.id!==seenPdf) {
          seenPdf=args.arquivoPdf.id;
          if(!STATE.pendingAction || STATE.pendingAction.id===seenPdf) {
            STATE.readyPdfFile={...args.arquivoPdf,escopo:'Clientes pendentes'};
            const solicitadoAgora=pdfSolicitadoAgora;
            if(solicitadoAgora)STATE.pendingAction=null;
            if(solicitadoAgora)triggerBase64PdfDownload(args.arquivoPdf.nome,args.arquivoPdf.base64);
          }
        }
        if(!args.arquivoPdf)STATE.readyPdfFile=null;
        lastRenderSignature=signature;renderRadar();
      } catch(error) {
        console.error('Falha no contrato da interface:',error.message);
        document.getElementById('radarAppRoot').innerHTML='<div class="status-banner error">Não foi possível preparar a tela. Recarregue a página e confira a versão instalada.</div>';
        adjustStreamlitFrameHeight();
      }
    });
    

    function triggerBase64PdfDownload(filename,b64Data) {
      try {
        const bytes=Uint8Array.from(atob(b64Data),c=>c.charCodeAt(0));
        const url=URL.createObjectURL(new Blob([bytes],{type:'application/pdf'}));
        const link=document.createElement('a');link.href=url;link.download=filename;
        document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
      } catch(e) {console.warn('PDF disponível pelo botão de download.');}
    }
    

    /*************************************************************************
     * 5. LÓGICA DE FILTRAGEM, RECORTES E ORDENAÇÃO ESTÁVEL
     *************************************************************************/
    function getFilteredAndSortedClients() {
      const p = STATE.payload && RadarContrato.escopo(STATE.payload,STATE);
      if (!p) return { totalBase: 0, list: [] };

      // 1. Escolhe a fonte conforme o recorte selecionado:
      // "cadastrados_mes" usa a lista separada fora da janela de 12m!
      let sourceList = STATE.activeRecorte === "cadastrados_mes"
        ? (p.cadastros_mes_lista || [])
        : (p.clientes || []);

      

    const totalBase = sourceList.length;

      // 2. Aplica o recorte comercial principal
      let filtered = sourceList.filter(c => {
        if (STATE.activeRecorte === "prioridades") return Boolean(c.prioridade_comercial);
        if (STATE.activeRecorte === "retomar") return Boolean(c.retomar_contato);
        if (STATE.activeRecorte === "cadastrados_mes") {
          if (STATE.subFiltroCadastrosMes === "ja_compraram") return Boolean(c.ja_comprou_primeira_vez || c.comprou_mes);
          if (STATE.subFiltroCadastrosMes === "sem_primeira_compra") return !(c.ja_comprou_primeira_vez || c.comprou_mes);
          return true;
        }
        return true; // "todos"
      });

      // 3. Busca textual (nome, razão social ou código)
      const q=RadarContrato.normalizar(STATE.searchQuery.trim());
      if (q) {
        filtered = filtered.filter(c =>
          RadarContrato.normalizar(c.nome).includes(q) ||
          RadarContrato.normalizar(c.nome_fantasia).includes(q) ||
          RadarContrato.normalizar(c.codigo).includes(q)
        );
      }

      // 4. Filtro de Curva ABC
      if (STATE.filtroCurva !== "TODAS") {
        filtered = filtered.filter(c => c.curva === STATE.filtroCurva);
      }

      // 5. Filtro de Situação no Mês
      if (STATE.filtroSituacaoMes !== "TODAS") {
        filtered = filtered.filter(c => {
          const compra = Number(c.compra_mes || 0);
          const media = Number(c.media_mensal || 0);
          if (STATE.filtroSituacaoMes === "nao_comprou") return !c.comprou_mes;
          if(STATE.filtroSituacaoMes==="abaixo_media")return RadarContrato.situacao(c)==="abaixo_media";
          if(STATE.filtroSituacaoMes==="mais_20_abaixo")return c.comprou_mes&&c.abaixo_20;
          if(STATE.filtroSituacaoMes==="na_media")return RadarContrato.situacao(c)==="na_media";
          if(STATE.filtroSituacaoMes==="acima_media")return RadarContrato.situacao(c)==="acima_media";
          return true;
        });
      }

      // 6. Filtros Avançados ("Mais filtros")
      // 6.1 Dois meses de calendário (critério distinto de 60 dias!)
      if (STATE.filtroDoisMesesCal !== "TODOS") {
        filtered = filtered.filter(c =>
          STATE.filtroDoisMesesCal === "com_compra_2m"
            ? Boolean(c.comprou_ultimos_2m_calendario)
            : !Boolean(c.comprou_ultimos_2m_calendario)
        );
      }

      // 6.2 Período da última compra
      if (STATE.filtroPeriodoUltima !== "TODOS") {
        filtered = filtered.filter(c => c.periodo_ultima === STATE.filtroPeriodoUltima);
      }

      // 6.3 Dias sem comprar
      if (STATE.filtroDiasSemComprar !== "TODOS") {
        filtered = filtered.filter(c => {
          const d = c.dias_sem_comprar;
          if (STATE.filtroDiasSemComprar === "sem_12m") return d === null || d === undefined;
          if (d === null || d === undefined) return false;
          if (STATE.filtroDiasSemComprar === "ate_30") return d <= 30;
          if (STATE.filtroDiasSemComprar === "31_60") return d >= 31 && d <= 60;
          if (STATE.filtroDiasSemComprar === "61_120") return d >= 61 && d <= 120;
          if (STATE.filtroDiasSemComprar === "mais_120") return d > 120;
          return true;
        });
      }

      // 6.4 Faixa de Média Mensal
      if (STATE.filtroFaixaMedia !== "TODAS") {
        filtered = filtered.filter(c => {
          const m = Number(c.media_mensal || 0);
          if (STATE.filtroFaixaMedia === "ate_1500") return m <= 1500;
          if (STATE.filtroFaixaMedia === "1500_3500") return m > 1500 && m <= 3500;
          if (STATE.filtroFaixaMedia === "acima_3500") return m > 3500;
          return true;
        });
      }

      // 6.5 Valor da Última Compra
      if (STATE.filtroValorUltima !== "TODOS") {
        filtered = filtered.filter(c => {
          if(c.ultima_compra_valor==null)return false;
          const u = Number(c.ultima_compra_valor);
          if (STATE.filtroValorUltima === "ate_1500") return u <= 1500;
          if (STATE.filtroValorUltima === "1500_3500") return u > 1500 && u <= 3500;
          if (STATE.filtroValorUltima === "acima_3500") return u > 3500;
          return true;
        });
      }

      // 6.6 Diferença para a Média
      if (STATE.filtroDifMedia !== "TODAS") {
        filtered = filtered.filter(c => {
          const dif = Number(c.compra_mes || 0) - Number(c.media_mensal || 0);
          if (STATE.filtroDifMedia === "mais_2000_abaixo") return dif < -2000;
          if (STATE.filtroDifMedia === "ate_2000_abaixo") return dif < 0 && dif >= -2000;
          if (STATE.filtroDifMedia === "igual_acima") return dif >= 0;
          return true;
        });
      }

      // 7. Ordenação com desempate estável por código
      filtered.sort((a, b) => {
        let cmp = 0;
        if (STATE.ordenacao === "az") {
          cmp = RadarContrato.comparar(a,b);
        } else if (STATE.ordenacao === "prioridade") {
          cmp = a.ordem_status-b.ordem_status || b.receita_risco-a.receita_risco;
        } else if (STATE.ordenacao === "maior_media") {
          cmp = Number(b.media_mensal || 0) - Number(a.media_mensal || 0);
        } else if (STATE.ordenacao === "maior_tempo") {
          const da = a.dias_sem_comprar === null ? 9999 : Number(a.dias_sem_comprar);
          const db = b.dias_sem_comprar === null ? 9999 : Number(b.dias_sem_comprar);
          cmp = db - da;
        } else if (STATE.ordenacao === "maior_dif_abaixo") {
          const difA = Number(a.media_mensal || 0) - Number(a.compra_mes || 0);
          const difB = Number(b.media_mensal || 0) - Number(b.compra_mes || 0);
          cmp = difB - difA;
        }
        if (cmp !== 0) return cmp;
        return RadarContrato.comparar(a,b);
      });

      return { totalBase, list: filtered };
    }

    function getActiveFilterChips() {
      const chips = [];
      if (STATE.searchQuery.trim()) chips.push({ key: "searchQuery", label: `Busca: "${STATE.searchQuery.trim()}"`, reset: "" });
      if (STATE.filtroCurva !== "TODAS") chips.push({ key: "filtroCurva", label: `Curva ${STATE.filtroCurva}`, reset: "TODAS" });

      const mapSituacao = {
        nao_comprou: "Ainda não comprou",
        abaixo_media: "Abaixo da média",
        mais_20_abaixo: "> 20% abaixo da média",
        na_media: "Na média",
        acima_media: "Acima da média"
      };
      if (STATE.filtroSituacaoMes !== "TODAS") {
        chips.push({ key: "filtroSituacaoMes", label: `Situação: ${mapSituacao[STATE.filtroSituacaoMes]}`, reset: "TODAS" });
      }

      const map2m = { com_compra_2m: "Com compra nos últimos 2m cal.", sem_compra_2m: "Sem compra nos últimos 2m cal." };
      if (STATE.filtroDoisMesesCal !== "TODOS") {
        chips.push({ key: "filtroDoisMesesCal", label: map2m[STATE.filtroDoisMesesCal], reset: "TODOS" });
      }

      const mapPer = { neste_mes: "Última: Neste mês", mes_anterior: "Última: Mês anterior", entre_2_4m: "Última: 2 a 4 meses", mais_4m: "Última: > 4 meses", sem_12m: "Última: Sem compra 12m" };
      if (STATE.filtroPeriodoUltima !== "TODOS") {
        chips.push({ key: "filtroPeriodoUltima", label: mapPer[STATE.filtroPeriodoUltima], reset: "TODOS" });
      }

      const mapDias = { ate_30: "Até 30 dias s/ comprar", "31_60": "31–60 dias s/ comprar", "61_120": "61–120 dias s/ comprar", mais_120: "> 120 dias s/ comprar", sem_12m: "Sem compra 12m" };
      if (STATE.filtroDiasSemComprar !== "TODOS") {
        chips.push({ key: "filtroDiasSemComprar", label: mapDias[STATE.filtroDiasSemComprar], reset: "TODOS" });
      }

      const mapMedia = { ate_1500: "Média: Até R$ 1.500", "1500_3500": "Média: R$ 1.500–3.500", acima_3500: "Média: > R$ 3.500" };
      if (STATE.filtroFaixaMedia !== "TODAS") {
        chips.push({ key: "filtroFaixaMedia", label: mapMedia[STATE.filtroFaixaMedia], reset: "TODAS" });
      }

      const mapUlt = { ate_1500: "Últ. compra: Até R$ 1.500", "1500_3500": "Últ. compra: R$ 1.500–3.500", acima_3500: "Últ. compra: > R$ 3.500" };
      if (STATE.filtroValorUltima !== "TODOS") {
        chips.push({ key: "filtroValorUltima", label: mapUlt[STATE.filtroValorUltima], reset: "TODOS" });
      }

      const mapDif = { mais_2000_abaixo: "Dif. média: > R$ 2.000 abaixo", ate_2000_abaixo: "Dif. média: Até R$ 2.000 abaixo", igual_acima: "Dif. média: Igual ou acima" };
      if (STATE.filtroDifMedia !== "TODAS") {
        chips.push({ key: "filtroDifMedia", label: mapDif[STATE.filtroDifMedia], reset: "TODAS" });
      }

      return chips;
    }

    function clearAllClientFilters() {
      STATE.searchQuery = "";
      STATE.filtroCurva = "TODAS";
      STATE.filtroSituacaoMes = "TODAS";
      STATE.filtroDoisMesesCal = "TODOS";
      STATE.filtroPeriodoUltima = "TODOS";
      STATE.filtroDiasSemComprar = "TODOS";
      STATE.filtroFaixaMedia = "TODAS";
      STATE.filtroValorUltima = "TODOS";
      STATE.filtroDifMedia = "TODAS";
      STATE.ordenacao = "az";
      STATE.currentPage = 1;
      renderRadar();
    }

    /*************************************************************************
     * 6. RENDERIZAÇÃO MODULAR DA INTERFACE (PRESERVANDO FOCO E SCROLL)
     *************************************************************************/
    function renderRadar() {
      const root = document.getElementById("radarAppRoot");
      if (!root) return;

      // Captura elemento ativo e posição do cursor para preservar foco durante digitação
      STATE.formDrafts=STATE.formDrafts||{};
      if(!STATE.skipDraftCapture) document.querySelectorAll('[data-draft-scope] input,[data-draft-scope] select,[data-draft-scope] textarea').forEach(el=>{
        if(el.id)STATE.formDrafts[el.closest('[data-draft-scope]').dataset.draftScope+'|'+el.id]=el.type==='checkbox'?el.checked:el.value;
      });
      STATE.skipDraftCapture=false;
      const activeEl = document.activeElement;
      const focusId = activeEl && activeEl.id ? activeEl.id : null;
      const selectionStart = activeEl && typeof activeEl.selectionStart === "number" ? activeEl.selectionStart : null;
      const selectionEnd = activeEl && typeof activeEl.selectionEnd === "number" ? activeEl.selectionEnd : null;
      const scrollY = window.scrollY;

      const p = STATE.payload;
      if (!p) {
        root.innerHTML = renderSkeletonView();
        adjustStreamlitFrameHeight();
        return;
      }

      const htmlParts = [
        renderHeader(p),
        renderGlobalBanners(p),
        p.usuario.perfil !== "vendedora" ? renderRoleNavigation(p) : "",
        renderMainViewByTab(RadarContrato.escopo(p,STATE))
      ];

      root.innerHTML = htmlParts.join("");
      renderActiveModal();
      bindInteractiveEvents();
      document.querySelectorAll('[data-draft-scope] input,[data-draft-scope] select,[data-draft-scope] textarea').forEach(el=>{
        const key=el.closest('[data-draft-scope]').dataset.draftScope+'|'+el.id;
        if(Object.prototype.hasOwnProperty.call(STATE.formDrafts,key)) {
          if(el.type==='checkbox')el.checked=STATE.formDrafts[key];else el.value=STATE.formDrafts[key];
        }
      });

      // Restaura foco e posição exata do cursor se o usuário estava digitando
      if (focusId) {
        const restored = document.getElementById(focusId);
        if (restored) {
          restored.focus({preventScroll:true});
          if (selectionStart !== null && typeof restored.setSelectionRange === "function") {
            try { restored.setSelectionRange(selectionStart, selectionEnd); } catch (e) {}
          }
        }
      }
      window.scrollTo(0, scrollY);
      adjustStreamlitFrameHeight();
    }

    function renderSkeletonView() {
      return `
        <div class="radar-header">
          <div class="brand-group">
            <div class="gm-logo">GM</div>
            <div class="brand-titles">
              <div class="brand-name">Radar Comercial • GM Limpezas</div>
              <div class="brand-sub">Carregando estrutura comercial...</div>
            </div>
          </div>
        </div>
        <div class="top-kpi-strip">
          <div class="surface-card"><div class="skeleton-box" style="height: 105px;"></div></div>
          <div class="surface-card"><div class="skeleton-box" style="height: 105px;"></div></div>
        </div>
        <div class="surface-card abc-section"><div class="skeleton-box" style="height: 120px;"></div></div>
        <div class="clients-workspace"><div class="skeleton-box" style="height: 320px;"></div></div>
      `;
    }

    /* 6.1 CABEÇALHO BAIXO */
    function renderHeader(p) {
      const roleLabels = {
        vendedora: "Vendedora",
        supervisao: "Supervisão",
        gestao: "Gestão"
      };
      return `
        <header class="radar-header">
          <div class="brand-group">
            <div class="gm-logo" aria-hidden="true">${p.raw.logo?`<img src="${escapeHtml(p.raw.logo)}" alt="">`:"GM"}</div>
            <div class="brand-titles">
              <div class="brand-name">
                <span>Radar Comercial</span>
                <span style="font-weight:400; opacity:0.8;">• GM Limpezas</span>
              </div>
              <div class="brand-sub">
                Base atualizada em <strong>${escapeHtml(p.atualizado_em)}</strong> • Aberto às ${escapeHtml(STATE.pageOpenedAt)} (America/Sao_Paulo)
              </div>
            </div>
          </div>

          <div class="header-meta">
            <div class="header-pill" title="Usuária autenticada e perfil de acesso">
              <span>Usuária:</span>
              <strong>${escapeHtml(p.usuario.nome)}</strong>
              <span style="opacity:0.85;">(${escapeHtml(roleLabels[p.usuario.perfil] || p.usuario.perfil)})</span>
            </div>
            <div class="header-pill" title="Mês comercial de referência dos dados">
              <span>Mês:</span>
              <strong>${escapeHtml(p.mes_referencia)}</strong>
            </div>
            <button type="button" class="btn-header" id="btnRelerArquivos" data-action="reler_arquivos" title="Reler arquivos e caches locais do servidor" ${STATE.pendingAction&&!STATE.pendingAction.timedOut ? "disabled" : ""}>
              <span>↻ Reler arquivos</span>
            </button>
            <button type="button" class="btn-header" id="btnOpenDiagnostico" title="Informações da base, versão e diagnóstico">
              <span>Base & Ajuda</span>
            </button>
            <button type="button" class="btn-header btn-logout" id="btnSairRadar" data-action="sair_radar" title="Encerrar sessão no Radar Comercial">
              <span>Sair</span>
            </button>
          </div>
        </header>
      `;
    }

    /* 6.2 BANNERS DE ALERTA, FEEDBACK ASSÍNCRONO E PDF PRONTO */
    function renderGlobalBanners(p) {
      const banners = [];

      if (false) {
        banners.push(`
          <div class="status-banner warning" role="alert">
            <div>
              <strong>Atenção • Base desatualizada:</strong> A última sincronização com o Cronos ocorreu em <strong>${escapeHtml(p.atualizado_em)}</strong>. Confira se o processo de atualização foi executado antes de emitir cobranças finais.
            </div>
            <button type="button" class="btn btn-xs" data-trigger="reler_acessos">Reler arquivos locais</button>
          </div>
        `);
      }

      if (STATE.pendingAction) {
        banners.push(`
          <div class="status-banner info" role="status">
            <div>
              <strong>⏳ ${escapeHtml(STATE.pendingAction.label)}</strong> Aguarde a confirmação.
            </div>
          </div>
        `);
      }

      if (STATE.lastFeedback) {
        banners.push(`
          <div class="status-banner ${escapeHtml(STATE.lastFeedback.status)}" role="status">
            <div>${escapeHtml(STATE.lastFeedback.message)}</div>
            <button type="button" class="btn btn-xs" id="btnDismissFeedback">Fechar aviso</button>
          </div>
        `);
      }

      if (STATE.readyPdfFile) {
        banners.push(`
          <div class="status-banner success" role="region" aria-label="Download do PDF pronto">
            <div>
              <strong>📄 PDF de clientes pendentes pronto (${escapeHtml(STATE.readyPdfFile.escopo)}):</strong>
              Caso o download automático não tenha iniciado no navegador, utilize o botão ao lado.
            </div>
            <div style="display:flex; gap:6px;">
              <a class="btn btn-xs btn-primary" href="data:application/pdf;base64,${escapeHtml(STATE.readyPdfFile.base64)}" download="${escapeHtml(STATE.readyPdfFile.nome)}">
                ⬇ Baixar ${escapeHtml(STATE.readyPdfFile.nome)}
              </a>
              <button type="button" class="btn btn-xs" id="btnClosePdfBanner">Ocultar</button>
            </div>
          </div>
        `);
      }

      for(const aviso of p.avisos||[]) banners.push(`<div class="status-banner warning" role="status">${escapeHtml(aviso)}</div>`);
      if (!banners.length) return "";
      return `<div class="banners-stack">${banners.join("")}</div>`;
    }

    /* 6.3 NAVEGAÇÃO DE SUPERVISÃO E GESTÃO (VISÃO GERAL PRIMEIRO + DEMAIS EM ORDEM ALFABÉTICA) */
    function renderRoleNavigation(p) {
      const isGestao = p.usuario.perfil === "gestao";

      // Visão geral SEMPRE primeiro; demais menus em estrita ordem alfabética:
      const tabsSupervisao = [
        { id: "visao_geral", label: "Visão geral" },
        { id: "carteira_geral", label: "Carteira geral" },
        { id: "desempenho", label: "Desempenho comparativo" },
        { id: "documentos", label: "Documentos em aberto" },
        { id: "metas", label: "Metas mensais" }
      ];

      const tabsGestao = [
        { id: "visao_geral", label: "Visão geral" },
        { id: "cadastros_fora", label: "Cadastros fora da carteira" },
        { id: "carteira_geral", label: "Carteira geral" },
        { id: "desempenho", label: "Desempenho comparativo" },
        { id: "documentos", label: "Documentos em aberto" },
        { id: "equipe_radar", label: "Equipe do Radar" },
        { id: "metas", label: "Metas mensais" },
        { id: "perfis_acessos", label: "Perfis e acessos" }
      ];

      const tabs = isGestao ? tabsGestao : tabsSupervisao;
      const supervisores=p.raw.supervisores||[];
      const vendedorasAtivas=(p.vendedores_equipe||[]).filter(v=>STATE.selectedTeamSupervisor==="TODOS"||v.id_equipe===STATE.selectedTeamSupervisor);

      return `
        <nav class="role-nav-bar" aria-label="Navegação de Supervisão e Gestão">
          <div class="role-tabs">
            ${tabs.map(t => `
              <button type="button" class="role-tab-btn ${STATE.activeRoleTab === t.id ? "active" : ""}" data-role-tab="${t.id}">
                ${escapeHtml(t.label)}
              </button>
            `).join("")}
          </div>

          <div class="scope-selectors">
            ${isGestao ? `
              <label for="selFilterSupervisor">Equipe:</label>
              <select id="selFilterSupervisor" class="select-compact">
                <option value="TODOS" ${STATE.selectedTeamSupervisor === "TODOS" ? "selected" : ""}>Todas as equipes</option>
                ${supervisores.map(s => `<option value="${escapeHtml(s.IdEquipe)}" ${STATE.selectedTeamSupervisor===s.IdEquipe?"selected":""}>${escapeHtml(s.Nome)}</option>`).join("")}
              </select>
            ` : ""}

            <label for="selFilterVendedora">Vendedora:</label>
            <select id="selFilterVendedora" class="select-compact">
              <option value="TODAS" ${STATE.selectedVendedoraCodigo === "TODAS" ? "selected" : ""}>Todas no escopo (${vendedorasAtivas.length})</option>
              ${vendedorasAtivas.map(v => `
                <option value="${escapeHtml(v.codigo)}" ${String(STATE.selectedVendedoraCodigo) === String(v.codigo) ? "selected" : ""}>
                  ${escapeHtml(v.nome)} (#${escapeHtml(v.codigo)})
                </option>
              `).join("")}
            </select>
            ${STATE.selectedVendedoraCodigo !== "TODAS" ? `
              <button type="button" class="btn btn-xs" id="btnResetVendedoraScope">Ver equipe completa</button>
            ` : ""}
          </div>
        </nav>
      `;
    }

    /* 6.4 ROTEADOR DE ABAS */
    function renderMainViewByTab(p) {
      if (p.usuario.perfil === "vendedora") {
        return `
          ${renderTopKpiStrip(p)}
          ${renderAbcProgressBlock(p)}
          ${renderClientsWorkspace(p)}
        `;
      }

      // Supervisão ou Gestão
      switch (STATE.activeRoleTab) {
        case "visao_geral":
          return `
            ${renderTopKpiStrip(p)}
            ${p.usuario.perfil === "gestao" ? renderCronosReconciliationCard(p) : ""}
            ${renderAbcProgressBlock(p)}
            ${renderComparativePerformanceTable(p, true)}
            ${renderClientsWorkspace(p)}
          `;
        case "carteira_geral":
          return `
            ${renderAbcProgressBlock(p)}
            ${renderClientsWorkspace(p)}
          `;
        case "desempenho":
          return renderComparativePerformanceTable(p, false);
        case "documentos":
          return renderOpenDocumentsTab(p);
        case "metas":
          return renderMetasMensaisTab(p);
        case "cadastros_fora":
          return renderCadastrosForaCarteiraTab(p);
        case "equipe_radar":
          return renderEquipeDoRadarTab(p);
        case "perfis_acessos":
          return renderPerfisEAcessosTab(p);
        default:
          return renderTopKpiStrip(p);
      }
    }

    /* 6.5 FAIXA COMPACTA DE INDICADORES PRINCIPAIS (RESULTADO + RESUMO COMERCIAL) */
    function renderTopKpiStrip(p) {
      const r=p.resumo;
      const realizado=r.somaRealizado, meta=r.somaMeta, rentabilidade=r.rentabilidadeConsolidada;
      const tituloEscopo=p.vendedores_equipe.length===1?`Resultado • ${p.vendedores_equipe[0].nome}`:'Resultado do mês • Equipe selecionada';
      

    const temMeta = meta!=null && meta>0 && realizado!=null;
      const pctAtingido = temMeta ? (realizado / meta) * 100 : null;
      const diferencaMeta = temMeta ? realizado - meta : null;

      let labelRestanteOuExcedido = realizado==null?"Faturamento indisponível":"Meta não definida";
      let valorRestanteOuExcedido = realizado==null?"Indisponível":"Meta não definida";
      let statusPillClass = "pill-neutral";
      let barColorClass = "";

      if (temMeta) {
        if (diferencaMeta >= 0) {
          labelRestanteOuExcedido = "Valor excedido";
          valorRestanteOuExcedido = `+ ${formatCurrency(diferencaMeta)}`;
          statusPillClass = "pill-green";
          barColorClass = "green";
        } else {
          labelRestanteOuExcedido = "Falta para a meta";
          valorRestanteOuExcedido = formatCurrency(Math.abs(diferencaMeta));
          statusPillClass = pctAtingido >= 70 ? "pill-amber" : "pill-red";
          barColorClass = pctAtingido >= 70 ? "amber" : "";
        }
      }

      // Contadores do Resumo Comercial (sem repetição em cards gigantes)
      const clientesEscopo=p.clientes||[];

      const totalCarteira = clientesEscopo.length;
      const compraramMes = clientesEscopo.filter(c => c.comprou_mes).length;
      const semCompraMes = Math.max(0, totalCarteira - compraramMes);
      const qtdPrioridades = clientesEscopo.filter(c => Boolean(c.prioridade_comercial)).length;
      const qtdCadastrosMes=p.cadastroCompleto?(p.cadastros_mes_lista||[]).length:"Indisponível";
      const qtdOrcamentos=p.documentosDisponiveis.orcamentos?(p.orcamentos_abertos_lista||[]).length:"Indisponível";
      const qtdPrevendas=p.documentosDisponiveis.prevendas?(p.prevendas_abertas_lista||[]).length:"Indisponível";

      const pctBarra = temMeta ? Math.min(100, Math.max(0, pctAtingido)) : 0;

      return `
        <section class="top-kpi-strip" aria-label="Indicadores principais e resumo comercial">
          <!-- CARD 1: RESULTADO DO MÊS -->
          <div class="surface-card">
            <div class="card-header-row">
              <span class="section-title">${escapeHtml(tituloEscopo)}</span>
              <span class="meta-status-pill ${statusPillClass}">
                ${temMeta ? `${formatPercent(pctAtingido, 1)} • ${escapeHtml(pctAtingido>=100?"Meta atingida":"Em andamento")}` : (meta!=null?"Faturamento indisponível":"Meta não definida")}
              </span>
            </div>

            <div class="resultado-main-grid">
              <div class="metric-cell">
                <span class="metric-label">Faturamento realizado</span>
                <span class="metric-val-lg">${formatCurrency(realizado)}</span>
              </div>
              <div class="metric-cell">
                <span class="metric-label">Meta mensal</span>
                <span class="metric-val-md">${meta!=null ? formatCurrency(meta) : "Meta não definida"}</span>
              </div>
              <div class="metric-cell">
                <span class="metric-label">${escapeHtml(labelRestanteOuExcedido)}</span>
                <span class="metric-val-md" style="color: ${temMeta && diferencaMeta >= 0 ? "var(--sem-green-text)" : "var(--gm-navy)"};">
                  ${escapeHtml(valorRestanteOuExcedido)}
                </span>
              </div>
              <div class="metric-cell">
                <span class="metric-label">Rentabilidade</span>
                <span class="metric-val-md">${rentabilidade !== null && rentabilidade !== undefined ? formatPercent(rentabilidade, 1) : "Indisponível"}</span>
              </div>
            </div>

            <div class="progress-track" role="progressbar" aria-valuenow="${temMeta ? Math.round(pctBarra) : 0}" aria-valuetext="${temMeta?formatPercent(pctAtingido):'Meta ou faturamento indisponível'}" aria-valuemin="0" aria-valuemax="100">
              <div class="progress-fill ${barColorClass}" style="width: ${pctBarra}%;"></div>
            </div>

            <div class="resultado-footer">
              <span>${!p.vendedores_equipe.length?"Sem vendedoras neste recorte.":!r.todasTemMeta?`Defina as metas de ${r.vendedorasSemMeta?.length??0} vendedora(s) para acompanhar o percentual da equipe.`:"Mês parcial: compra abaixo da média indica oportunidade de complemento."}</span>
              <span>Atualização: <strong>${escapeHtml(p.atualizado_em)}</strong></span>
            </div>
          </div>

          <!-- CARD 2: RESUMO COMERCIAL ACIONÁVEL -->
          <div class="surface-card">
            <div class="card-header-row">
              <span class="section-title">Resumo Comercial & Ações Rápidas</span>
              <span style="font-size:11.5px; color:var(--gm-text-muted);">Clique para filtrar ou consultar</span>
            </div>

            <div class="resumo-comercial-grid">
              <button type="button" class="resumo-action-box ${STATE.activeRecorte === "todos" ? "active-box" : ""}" data-quick-recorte="todos" title="Ver todos os clientes da carteira ativa">
                <span class="resumo-box-title">Carteira (12m)</span>
                <span class="resumo-box-num">${compraramMes} <span style="font-size:13px; font-weight:600; color:var(--gm-text-secondary);">/ ${totalCarteira}</span></span>
                <span class="resumo-box-foot">${semCompraMes} sem compra no mês</span>
              </button>

              <button type="button" class="resumo-action-box ${STATE.activeRecorte === "prioridades" ? "active-box" : ""}" data-quick-recorte="prioridades" title="Focar nos clientes em Prioridades comerciais">
                <span class="resumo-box-title">Prioridades</span>
                <span class="resumo-box-num" style="color:var(--sem-red-text);">${qtdPrioridades}</span>
                <span class="resumo-box-foot">Ver quem precisa de atenção →</span>
              </button>

              <button type="button" class="resumo-action-box ${STATE.activeRecorte === "cadastrados_mes" ? "active-box" : ""}" data-quick-recorte="cadastrados_mes" title="Ver clientes cadastrados neste mês (separado da carteira 12m)">
                <span class="resumo-box-title">Cadastrados no mês</span>
                <span class="resumo-box-num">${qtdCadastrosMes}</span>
                <span class="resumo-box-foot">Consultar novos cadastros →</span>
              </button>

              <div class="resumo-action-box">
                <span class="resumo-box-title">Em aberto (Não faturado)</span>
                <div style="display:flex; flex-direction:column; gap:4px; margin-top:2px;">
                  <button type="button" class="btn btn-xs" id="btnOpenOrcamentosModal" style="justify-content:space-between;">
                    <span>Orçamentos</span>
                    <strong>${qtdOrcamentos}</strong>
                  </button>
                  <button type="button" class="btn btn-xs" id="btnOpenPrevendasModal" style="justify-content:space-between;">
                    <span>Pré-vendas</span>
                    <strong>${qtdPrevendas}</strong>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </section>
      `;
    }

    /* 6.6 PROGRESSO DA CARTEIRA POR CURVA ABC (SEM GRÁFICO DE PIZZA) */
    function renderAbcProgressBlock(p) {
      const curvas = p.curvas_abc || [];
      return `
        <section class="surface-card abc-section" aria-label="Progresso da carteira por curva ABC">
          <div class="card-header-row">
            <div>
              <span class="section-title">Progresso da Carteira por Curva ABC</span>
              <span style="font-size:11.5px; color:var(--gm-text-muted); margin-left:8px;">
                Classificação global (A: 20% • B: 30% • C: 50%) — Apoio à ação e download de pendentes
              </span>
            </div>

            <div class="abc-header-actions">
              <button type="button" class="btn btn-xs" id="btnToggleAbcTable" aria-expanded="${STATE.showAbcTextTable}">
                <span>${STATE.showAbcTextTable ? "▾ Ocultar tabela textual" : "▸ Tabela textual acessível"}</span>
              </button>
              <button type="button" class="btn btn-xs" id="btnToggleAbcBaseInfo" aria-expanded="${STATE.showAbcBaseInfo}">
                <span>${STATE.showAbcBaseInfo ? "▾ Ocultar regra da carteira" : "Base e período da carteira"}</span>
              </button>
              <button type="button" class="btn btn-xs btn-primary" data-pdf-curva="TODAS" ${STATE.pendingAction ? "disabled" : ""}>
                <span>⬇ PDF de todas as curvas</span>
              </button>
            </div>
          </div>

          <div class="abc-cards-grid">
            ${curvas.map(c => {
              const isSelected = STATE.filtroCurva === c.curva;
              const semClientes = Number(c.total || 0) === 0;
              const pct = semClientes ? 0 : Number(c.percentual || 0);
              return `
                <div class="abc-card ${isSelected ? "filtered-curve" : ""}">
                  <div class="abc-card-top">
                    <span class="curve-badge curve-${escapeHtml(c.curva)}">Curva ${escapeHtml(c.curva)}</span>
                    <span style="font-size:12px; font-weight:700; color:var(--gm-navy);">
                      ${semClientes ? "Sem clientes" : `${formatPercent(pct, 1)} compraram`}
                    </span>
                  </div>

                  <div class="progress-track" style="height:6px; margin-bottom:2px;">
                    <div class="progress-fill ${pct >= 75 ? "green" : (pct >= 45 ? "" : "amber")}" style="width:${Math.min(100, pct)}%;"></div>
                  </div>

                  <div class="abc-numbers-row">
                    <span>Total: <strong>${c.total}</strong></span>
                    <span>Compraram: <strong style="color:var(--sem-green-text);">${c.compraram}</strong></span>
                    <span>Faltam: <strong style="color:var(--sem-red-text);">${c.faltam}</strong></span>
                  </div>

                  <div class="abc-actions-row">
                    <button type="button" class="btn btn-xs" data-act-curve-all="${escapeHtml(c.curva)}" ${semClientes ? "disabled" : ""}>
                      Ver clientes (${c.total})
                    </button>
                    <button type="button" class="btn btn-xs" data-act-curve-missing="${escapeHtml(c.curva)}" ${c.faltam <= 0 ? "disabled" : ""}>
                      Faltam comprar (${c.faltam})
                    </button>
                    <button type="button" class="btn btn-xs" data-pdf-curva="${escapeHtml(c.curva)}" ${c.faltam <= 0 || STATE.pendingAction ? "disabled" : ""} title="Baixar PDF dos clientes pendentes da Curva ${escapeHtml(c.curva)}">
                      ⬇ PDF pendentes
                    </button>
                  </div>
                </div>
              `;
            }).join("")}
          </div>

          ${STATE.showAbcTextTable ? `
            <div class="collapsible-panel" id="panelAbcTextTable">
              <div style="font-weight:700; margin-bottom:6px; color:var(--gm-navy);">Tabela Textual Acessível de Progresso por Curva</div>
              <div class="data-table-wrapper">
                <table class="clean-table" aria-label="Progresso detalhado por curva ABC">
                  <thead>
                    <tr>
                      <th>Curva</th>
                      <th>Critério Global</th>
                      <th>Total da Carteira</th>
                      <th>Compraram no Mês</th>
                      <th>Faltam Comprar</th>
                      <th>Percentual de Cobertura</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${curvas.map(c => `
                      <tr>
                        <td><strong>Curva ${escapeHtml(c.curva)}</strong></td>
                        <td>${escapeHtml(c.proporcao_regra || "-")}</td>
                        <td>${c.total}</td>
                        <td>${c.compraram}</td>
                        <td><strong>${c.faltam}</strong></td>
                        <td>${c.total > 0 ? formatPercent(c.percentual, 1) : "Sem clientes"}</td>
                      </tr>
                    `).join("")}
                  </tbody>
                </table>
              </div>
            </div>
          ` : ""}

          ${STATE.showAbcBaseInfo ? `
            <div class="collapsible-panel" id="panelAbcBaseInfo">
              <strong>Regras da Base e Período da Carteira Ativa:</strong>
              <ul style="margin-top:4px; padding-left:18px; display:flex; flex-direction:column; gap:3px;">
                <li><strong>Período de referência da carteira (12 meses):</strong> ${escapeHtml(p.periodo_carteira_12m)}.</li>
                <li><strong>Vínculo e faturamento:</strong> A carteira considera os clientes com compra nos 12 meses de calendário salvos e vínculo cadastral atual. O faturamento mensal é atribuído conforme o vendedor da movimentação conciliada com o Cronos.</li>
                <li><strong>Classificação ABC Global:</strong> Calculada no backend em grupos de 20% (Curva A), 30% (Curva B) e 50% (Curva C) dos clientes. A curva não é recalculada ao filtrar equipe ou vendedora.</li>
              </ul>
            </div>
          ` : ""}
        </section>
      `;
    }

    /* 6.7 ÁREA DE TRABALHO DE CLIENTES: RECORTES, BUSCA, FILTROS E LISTA PAGINADA */
    function renderClientsWorkspace(p) {
      const baseCarteira=p.clientes||[];

      const countPrioridades = baseCarteira.filter(c => c.prioridade_comercial).length;
      const countRetomar = baseCarteira.filter(c => c.retomar_contato).length;
      const countTodos = baseCarteira.length;
      const countCadMes=p.cadastroCompleto?(p.cadastros_mes_lista||[]).length:"—";

      const { totalBase, list: filteredClients } = getFilteredAndSortedClients();
      const activeChips = getActiveFilterChips();
      const moreFiltersCount = [
        STATE.filtroDoisMesesCal !== "TODOS",
        STATE.filtroPeriodoUltima !== "TODOS",
        STATE.filtroDiasSemComprar !== "TODOS",
        STATE.filtroFaixaMedia !== "TODAS",
        STATE.filtroValorUltima !== "TODOS",
        STATE.filtroDifMedia !== "TODAS"
      ].filter(Boolean).length;

      // Paginação de 25 clientes
      const totalPages = Math.max(1, Math.ceil(filteredClients.length / STATE.pageSize));
      if (STATE.currentPage > totalPages) STATE.currentPage = totalPages;
      const startIdx = (STATE.currentPage - 1) * STATE.pageSize;
      const pageItems = filteredClients.slice(startIdx, startIdx + STATE.pageSize);

      return `
        <section class="clients-workspace" id="clientsWorkspaceSection" aria-label="Carteira de clientes, filtros e ações">
          <!-- BARRA DE RECORTES COMERCIAIS (PRIORIDADES SELECIONADO POR PADRÃO) -->
          <div class="recortes-bar">
            <div class="recortes-pills" role="tablist" aria-label="Recortes comerciais de clientes">
              <button type="button" role="tab" aria-selected="${STATE.activeRecorte === "prioridades"}" class="recorte-pill ${STATE.activeRecorte === "prioridades" ? "active" : ""}" data-recorte="prioridades">
                <span>Prioridades</span>
                <span class="recorte-count">${countPrioridades}</span>
              </button>
              <button type="button" role="tab" aria-selected="${STATE.activeRecorte === "retomar"}" class="recorte-pill ${STATE.activeRecorte === "retomar" ? "active" : ""}" data-recorte="retomar">
                <span>Retomar contato</span>
                <span class="recorte-count">${countRetomar}</span>
              </button>
              <button type="button" role="tab" aria-selected="${STATE.activeRecorte === "cadastrados_mes"}" class="recorte-pill ${STATE.activeRecorte === "cadastrados_mes" ? "active" : ""}" data-recorte="cadastrados_mes">
                <span>Clientes cadastrados no mês</span>
                <span class="recorte-count">${countCadMes}</span>
              </button>
              <button type="button" role="tab" aria-selected="${STATE.activeRecorte === "todos"}" class="recorte-pill ${STATE.activeRecorte === "todos" ? "active" : ""}" data-recorte="todos">
                <span>Todos os clientes</span>
                <span class="recorte-count">${countTodos}</span>
              </button>
            </div>

            ${p.usuario.perfil !== "vendedora" ? `
              <div style="display:flex; align-items:center; gap:6px;">
                <button type="button" class="btn btn-xs ${STATE.supervisaoViewMode === "cards" ? "btn-primary" : ""}" data-view-mode="cards">Cartões</button>
                <button type="button" class="btn btn-xs ${STATE.supervisaoViewMode === "table" ? "btn-primary" : ""}" data-view-mode="table">Tabela</button>
                <button type="button" class="btn btn-xs" id="btnExportFilteredCsv">⬇ Exportar lista filtrada (CSV)</button>
              </div>
            ` : ""}
          </div>

          <!-- SUBFILTRO EXCLUSIVO QUANDO EM "CLIENTES CADASTRADOS NO MÊS" -->
          ${STATE.activeRecorte === "cadastrados_mes" ? `
            <div class="subfilter-strip">
              <div>
                <strong>Lista separada • Clientes cadastrados em ${escapeHtml(p.mes_referencia)}:</strong>
                <span>Baseada na data real de cadastro disponível (independente da janela de 12 meses).</span>
              </div>
              <div style="display:flex; gap:6px;">
                <button type="button" class="btn btn-xs ${STATE.subFiltroCadastrosMes === "todos" ? "btn-primary" : ""}" data-sub-cad="todos">Todos (${countCadMes})</button>
                <button type="button" class="btn btn-xs ${STATE.subFiltroCadastrosMes === "ja_compraram" ? "btn-primary" : ""}" data-sub-cad="ja_compraram">Já compraram</button>
                <button type="button" class="btn btn-xs ${STATE.subFiltroCadastrosMes === "sem_primeira_compra" ? "btn-primary" : ""}" data-sub-cad="sem_primeira_compra">Sem primeira compra</button>
              </div>
            </div>
          ` : ""}

          ${STATE.activeRecorte==='cadastrados_mes'&&!p.cadastroCompleto?'<div class="status-banner warning">Lista parcial: há datas de cadastro indisponíveis nesta base. Os registros conhecidos são mostrados abaixo.</div>':''}
          <!-- BUSCA, FILTROS ESSENCIAIS E ORDENAÇÃO SEMPRE À MÃO -->
          <div class="primary-filters-row">
            <div class="filter-field">
              <label for="inputClientSearch">Buscar cliente (Nome, Razão Social ou Código)</label>
              <input
                type="search"
                id="inputClientSearch"
                class="input-search"
                placeholder="Ex.: Hospital São Lucas, 4082..."
                value="${escapeHtml(STATE.searchQuery)}"
                autocomplete="off"
              />
            </div>

            <div class="filter-field">
              <label for="selFiltroCurva">Curva ABC</label>
              <select id="selFiltroCurva" class="select-filter">
                <option value="TODAS" ${STATE.filtroCurva === "TODAS" ? "selected" : ""}>Todas as curvas</option>
                <option value="A" ${STATE.filtroCurva === "A" ? "selected" : ""}>Curva A</option>
                <option value="B" ${STATE.filtroCurva === "B" ? "selected" : ""}>Curva B</option>
                <option value="C" ${STATE.filtroCurva === "C" ? "selected" : ""}>Curva C</option>
              </select>
            </div>

            <div class="filter-field">
              <label for="selFiltroSituacaoMes">Situação no mês</label>
              <select id="selFiltroSituacaoMes" class="select-filter">
                <option value="TODAS" ${STATE.filtroSituacaoMes === "TODAS" ? "selected" : ""}>Todas as situações</option>
                <option value="nao_comprou" ${STATE.filtroSituacaoMes === "nao_comprou" ? "selected" : ""}>Ainda não comprou</option>
                <option value="abaixo_media" ${STATE.filtroSituacaoMes === "abaixo_media" ? "selected" : ""}>Abaixo da média</option>
                <option value="mais_20_abaixo" ${STATE.filtroSituacaoMes === "mais_20_abaixo" ? "selected" : ""}>Mais de 20% abaixo da média</option>
                <option value="na_media" ${STATE.filtroSituacaoMes === "na_media" ? "selected" : ""}>Na média</option>
                <option value="acima_media" ${STATE.filtroSituacaoMes === "acima_media" ? "selected" : ""}>Acima da média</option>
              </select>
            </div>

            <div class="filter-field">
              <label for="selOrdenacao">Ordenação</label>
              <select id="selOrdenacao" class="select-filter">
                <option value="az" ${STATE.ordenacao === "az" ? "selected" : ""}>Nome A–Z (padrão)</option>
                <option value="prioridade" ${STATE.ordenacao === "prioridade" ? "selected" : ""}>Prioridade comercial</option>
                <option value="maior_media" ${STATE.ordenacao === "maior_media" ? "selected" : ""}>Maior média mensal</option>
                <option value="maior_tempo" ${STATE.ordenacao === "maior_tempo" ? "selected" : ""}>Maior tempo sem comprar</option>
                <option value="maior_dif_abaixo" ${STATE.ordenacao === "maior_dif_abaixo" ? "selected" : ""}>Maior diferença abaixo da média</option>
              </select>
            </div>

            <div class="filter-field">
              <button type="button" class="btn ${STATE.showMoreFilters || moreFiltersCount > 0 ? "btn-blue" : ""}" id="btnToggleMoreFilters" style="min-height:34px;">
                <span>⚙ Mais filtros${moreFiltersCount > 0 ? ` (${moreFiltersCount})` : ""}</span>
              </button>
            </div>
          </div>

          <!-- PAINEL EXPANSÍVEL "MAIS FILTROS" COM TODAS AS OPÇÕES EXISTENTES -->
          ${STATE.showMoreFilters ? `
            <div class="more-filters-drawer" id="drawerMoreFilters">
              <div class="filter-field">
                <label for="selDoisMesesCal">Últimos 2 meses de calendário</label>
                <select id="selDoisMesesCal" class="select-filter">
                  <option value="TODOS" ${STATE.filtroDoisMesesCal === "TODOS" ? "selected" : ""}>Todos</option>
                  <option value="com_compra_2m" ${STATE.filtroDoisMesesCal === "com_compra_2m" ? "selected" : ""}>Com compra nos últimos 2 meses cal.</option>
                  <option value="sem_compra_2m" ${STATE.filtroDoisMesesCal === "sem_compra_2m" ? "selected" : ""}>Sem compra nos últimos 2 meses cal.</option>
                </select>
              </div>

              <div class="filter-field">
                <label for="selPeriodoUltima">Período da última compra</label>
                <select id="selPeriodoUltima" class="select-filter">
                  <option value="TODOS" ${STATE.filtroPeriodoUltima === "TODOS" ? "selected" : ""}>Todos os períodos</option>
                  <option value="neste_mes" ${STATE.filtroPeriodoUltima === "neste_mes" ? "selected" : ""}>Neste mês</option>
                  <option value="mes_anterior" ${STATE.filtroPeriodoUltima === "mes_anterior" ? "selected" : ""}>No mês anterior</option>
                  <option value="entre_2_4m" ${STATE.filtroPeriodoUltima === "entre_2_4m" ? "selected" : ""}>Entre 2 e 4 meses</option>
                  <option value="mais_4m" ${STATE.filtroPeriodoUltima === "mais_4m" ? "selected" : ""}>Há mais de 4 meses</option>
                  <option value="sem_12m" ${STATE.filtroPeriodoUltima === "sem_12m" ? "selected" : ""}>Sem compra nos 12 meses</option>
                </select>
              </div>

              <div class="filter-field">
                <label for="selDiasSemComprar">Dias corridos sem comprar</label>
                <select id="selDiasSemComprar" class="select-filter">
                  <option value="TODOS" ${STATE.filtroDiasSemComprar === "TODOS" ? "selected" : ""}>Qualquer quantidade de dias</option>
                  <option value="ate_30" ${STATE.filtroDiasSemComprar === "ate_30" ? "selected" : ""}>Até 30 dias</option>
                  <option value="31_60" ${STATE.filtroDiasSemComprar === "31_60" ? "selected" : ""}>31–60 dias</option>
                  <option value="61_120" ${STATE.filtroDiasSemComprar === "61_120" ? "selected" : ""}>61–120 dias</option>
                  <option value="mais_120" ${STATE.filtroDiasSemComprar === "mais_120" ? "selected" : ""}>Mais de 120 dias</option>
                  <option value="sem_12m" ${STATE.filtroDiasSemComprar === "sem_12m" ? "selected" : ""}>Sem compra nos 12 meses</option>
                </select>
              </div>

              <div class="filter-field">
                <label for="selFaixaMedia">Média mensal (12m)</label>
                <select id="selFaixaMedia" class="select-filter">
                  <option value="TODAS" ${STATE.filtroFaixaMedia === "TODAS" ? "selected" : ""}>Todas as faixas</option>
                  <option value="ate_1500" ${STATE.filtroFaixaMedia === "ate_1500" ? "selected" : ""}>Até R$ 1.500</option>
                  <option value="1500_3500" ${STATE.filtroFaixaMedia === "1500_3500" ? "selected" : ""}>R$ 1.500,01–3.500</option>
                  <option value="acima_3500" ${STATE.filtroFaixaMedia === "acima_3500" ? "selected" : ""}>Acima de R$ 3.500</option>
                </select>
              </div>

              <div class="filter-field">
                <label for="selValorUltima">Valor da última compra</label>
                <select id="selValorUltima" class="select-filter">
                  <option value="TODOS" ${STATE.filtroValorUltima === "TODOS" ? "selected" : ""}>Todas as faixas</option>
                  <option value="ate_1500" ${STATE.filtroValorUltima === "ate_1500" ? "selected" : ""}>Até R$ 1.500</option>
                  <option value="1500_3500" ${STATE.filtroValorUltima === "1500_3500" ? "selected" : ""}>R$ 1.500,01–3.500</option>
                  <option value="acima_3500" ${STATE.filtroValorUltima === "acima_3500" ? "selected" : ""}>Acima de R$ 3.500</option>
                </select>
              </div>

              <div class="filter-field">
                <label for="selDifMedia">Diferença para a média</label>
                <select id="selDifMedia" class="select-filter">
                  <option value="TODAS" ${STATE.filtroDifMedia === "TODAS" ? "selected" : ""}>Todas</option>
                  <option value="mais_2000_abaixo" ${STATE.filtroDifMedia === "mais_2000_abaixo" ? "selected" : ""}>Mais de R$ 2.000 abaixo</option>
                  <option value="ate_2000_abaixo" ${STATE.filtroDifMedia === "ate_2000_abaixo" ? "selected" : ""}>Até R$ 2.000 abaixo</option>
                  <option value="igual_acima" ${STATE.filtroDifMedia === "igual_acima" ? "selected" : ""}>Igual ou acima da média</option>
                </select>
              </div>
            </div>
          ` : ""}

          <!-- RESUMO DO FILTRO E CHIPS ATIVOS -->
          <div class="active-filters-summary">
            <div class="filter-chips-list">
              <span>Exibindo <strong>${filteredClients.length}</strong> de <strong>${totalBase}</strong> clientes no recorte</span>
              ${activeChips.map(ch => `
                <span class="active-chip">
                  <span>${escapeHtml(ch.label)}</span>
                  <button type="button" data-remove-chip="${escapeHtml(ch.key)}" data-reset-val="${escapeHtml(ch.reset)}" title="Remover este filtro">×</button>
                </span>
              `).join("")}
            </div>
            ${activeChips.length > 0 || STATE.ordenacao !== "az" ? `
              <button type="button" class="btn btn-xs btn-ghost" id="btnClearAllFilters">Limpar filtros</button>
            ` : ""}
          </div>

          <!-- LISTA DE CLIENTES (CARTÕES COMPACTOS OU TABELA DE SUPERVISÃO) -->
          ${filteredClients.length === 0 ? renderEmptyClientsState(totalBase) : (
            p.usuario.perfil !== "vendedora" && STATE.supervisaoViewMode === "table"
              ? renderClientsTableMode(pageItems)
              : `<div class="clients-list">${pageItems.map(c => renderCompactClientCard(c, p)).join("")}</div>`
          )}

          <!-- PAGINAÇÃO DE 25 CLIENTES -->
          ${filteredClients.length > STATE.pageSize ? `
            <div class="pagination-bar">
              <span>Página <strong>${STATE.currentPage}</strong> de <strong>${totalPages}</strong> (25 clientes por página)</span>
              <div style="display:flex; gap:6px;">
                <button type="button" class="btn btn-xs" id="btnPrevPage" ${STATE.currentPage <= 1 ? "disabled" : ""}>← Anterior</button>
                <button type="button" class="btn btn-xs" id="btnNextPage" ${STATE.currentPage >= totalPages ? "disabled" : ""}>Próxima →</button>
              </div>
            </div>
          ` : ""}
        </section>
      `;
    }

    function renderEmptyClientsState(totalBase) {
      if (totalBase === 0) {
        return `
          <div style="padding:28px 16px; text-align:center; background:var(--gm-surface-alt); border:1px dashed var(--gm-border-strong); border-radius:var(--radius-sm);">
            <div style="font-size:15px; font-weight:700; color:var(--gm-navy); margin-bottom:4px;">Sem clientes neste escopo</div>
            <p style="color:var(--gm-text-secondary); font-size:13px;">Não há clientes vinculados a esta carteira ou recorte no momento.</p>
          </div>
        `;
      }
      return `
        <div style="padding:28px 16px; text-align:center; background:var(--gm-surface-alt); border:1px dashed var(--gm-border-strong); border-radius:var(--radius-sm);">
          <div style="font-size:15px; font-weight:700; color:var(--gm-navy); margin-bottom:4px;">Nenhum cliente encontrado com os filtros atuais</div>
          <p style="color:var(--gm-text-secondary); font-size:13px; margin-bottom:10px;">Experimente limpar os filtros ou alternar o recorte comercial acima.</p>
          <button type="button" class="btn btn-primary" id="btnEmptyResetFilters">Limpar todos os filtros</button>
        </div>
      `;
    }

    /* 6.8 CARD COMPACTO DE CLIENTE COM DETALHES SOB DEMANDA */
    function renderCompactClientCard(c, p) {
      const isExpanded = STATE.expandedClientCodes.has(String(c.codigo));
      const compraMes = Number(c.compra_mes || 0);
      const mediaMensal = Number(c.media_mensal || 0);
      const difMedia = compraMes - mediaMensal;
      const pctDif = mediaMensal > 0 ? (difMedia / mediaMensal) * 100 : null;

      let cardBorderClass = "status-ok";
      let reasonBadgeClass = "pill-green";
      if (c.prioridade_comercial && c.prioridade_nivel === "alta") {
        cardBorderClass = "priority-high";
        reasonBadgeClass = "pill-red";
      } else if (c.prioridade_comercial || compraMes < mediaMensal) {
        cardBorderClass = "priority-medium";
        reasonBadgeClass = "pill-amber";
      }

      const diasLabel = c.dias_sem_comprar !== null && c.dias_sem_comprar !== undefined
        ? `há ${c.dias_sem_comprar} dias`
        : "Sem compra 12m";

      return `
        <article class="client-card ${cardBorderClass}" data-client-code="${escapeHtml(c.codigo)}">
          <div class="client-main-row">
            <!-- IDENTIFICAÇÃO E MOTIVO COMERCIAL -->
            <div class="client-identity">
              <div class="client-title-line">
                <span class="curve-badge curve-${escapeHtml(c.curva)}">Curva ${escapeHtml(c.curva)}</span>
                <span class="client-name">${escapeHtml(c.nome)}</span>
                <span class="client-code">#${escapeHtml(c.codigo)}</span>
                ${p.usuario.perfil !== "vendedora" ? `
                  <span class="client-code" style="background:var(--gm-blue-light); color:var(--gm-navy); font-weight:600;">
                    Resp.: ${escapeHtml(c.vendedora_nome)}
                  </span>
                ` : ""}
              </div>

              ${c.motivo_comercial ? `
                <div class="client-reason-badge ${reasonBadgeClass}">
                  <span>${escapeHtml(c.motivo_comercial)}</span>
                </div>
              ` : ""}
            </div>

            <!-- INDICADORES DE COMPRA EM GRADE COMPACTA -->
            <div class="client-metrics-grid">
              <div class="c-metric">
                <span class="c-metric-lbl">Compra no mês</span>
                <span class="c-metric-val ${compraMes <= 0 ? "val-negative" : ""}">
                  ${formatCurrency(c.compra_mes)}${c.comprou_mes?"":" • Sem compra no mês"}
                </span>
                <span class="c-metric-sub">${p.mes_parcial && compraMes > 0 && compraMes < mediaMensal ? "Mês parcial" : "&nbsp;"}</span>
              </div>

              <div class="c-metric">
                <span class="c-metric-lbl">Média mensal (12m)</span>
                <span class="c-metric-val">${formatCurrency(c.media_mensal)}</span>
                <span class="c-metric-sub">Base 12 meses</span>
              </div>

              <div class="c-metric">
                <span class="c-metric-lbl">Dif. p/ média</span>
                <span class="c-metric-val ${difMedia < 0 ? "val-negative" : "val-positive"}">
                  ${c.media_mensal!=null ? `${difMedia >= 0 ? "+" : ""}${formatCurrency(difMedia)}` : "Indisponível"}
                </span>
                <span class="c-metric-sub">${pctDif !== null ? `(${pctDif >= 0 ? "+" : ""}${formatPercent(pctDif, 0)})` : "&nbsp;"}</span>
              </div>

              <div class="c-metric">
                <span class="c-metric-lbl">Última compra</span>
                <span class="c-metric-val">${escapeHtml(c.ultima_compra_data || "Indisponível")}</span>
                <span class="c-metric-sub">${c.ultima_compra_valor > 0 ? `${formatCurrency(c.ultima_compra_valor)} • ` : ""}<strong>${escapeHtml(diasLabel)}</strong></span>
              </div>
            </div>

            <!-- AÇÕES: CONTATO, WHATSAPP EDITÁVEL E DETALHES PERSISTENTES -->
            <div class="client-actions-col">
              <button type="button" class="btn btn-xs btn-whatsapp" data-whatsapp-client="${escapeHtml(c.codigo)}" ${!c.whatsapp?"disabled":""} title="Preparar mensagem editável no WhatsApp para ${escapeHtml(c.contato_nome || c.nome)}">
                <span>💬 WhatsApp</span>
              </button>
              <button type="button" class="btn btn-xs ${isExpanded ? "btn-primary" : ""}" data-toggle-details="${escapeHtml(c.codigo)}" aria-expanded="${isExpanded}">
                <span>${isExpanded ? "▾ Ocultar detalhes" : "▸ Detalhes"}</span>
              </button>
            </div>
          </div>

          ${isExpanded ? renderClientDetailsDrawer(c) : ""}
        </article>
      `;
    }

    function renderClientDetailsDrawer(c) {
      const hist = c.historico_12m || [];
      const prods = c.produtos_habituais || [];
      const docs = c.documentos_abertos || [];

      return `
        <div class="client-details-drawer">
          <!-- COLUNA 1: HISTÓRICO MENSAL 12M -->
          <div class="detail-box">
            <div class="detail-box-title">
              <span>Histórico Mensal (Últimos 12 meses)</span>
              <span>Rentabilidade: <strong>${c.rentabilidade !== null && c.rentabilidade !== undefined ? formatPercent(c.rentabilidade, 1) : "Indisponível"}</strong></span>
            </div>
            ${hist.length > 0 ? `
              <div class="history-mini-grid">
                ${hist.map(h => `
                  <div class="history-cell">
                    <span class="m-lbl">${escapeHtml(h.mes)}</span>
                    <span class="m-val" style="color:${Number(h.valor) <= 0 ? "var(--sem-red-text)" : "var(--gm-text)"};">
                      ${formatCurrency(h.valor)}
                    </span>
                  </div>
                `).join("")}
              </div>
            ` : `<p style="color:var(--gm-text-muted);">Sem movimentação faturada nos últimos 12 meses.</p>`}
          </div>

          <!-- COLUNA 2: PRODUTOS HABITUAIS E DOCUMENTOS EM ABERTO -->
          <div class="detail-box">
            <div class="detail-box-title">
              <span>Produtos Habituais & Documentos em Aberto</span>
            </div>
            ${prods.length > 0 ? `
              <div style="margin-bottom:8px;">
                <span style="font-size:11px; color:var(--gm-text-muted); font-weight:600;">Itens mais comprados:</span>
                <ul style="padding-left:16px; margin-top:2px;">
                  ${prods.map(pr => `<li>${escapeHtml(pr)}</li>`).join("")}
                </ul>
              </div>
            ` : `<p style="color:var(--gm-text-muted); margin-bottom:6px;">Produtos habituais: Indisponível.</p>`}

            <div style="border-top:1px solid var(--gm-border); padding-top:6px;">
              <span style="font-size:11px; color:var(--gm-text-muted); font-weight:600;">Orçamentos / Pré-vendas em aberto (${docs.length}):</span>
              ${docs.length > 0 ? docs.map(d => `
                <div style="margin-top:3px; padding:4px 6px; background:var(--gm-surface); border:1px solid var(--gm-border); border-radius:4px;">
                  <strong>${escapeHtml(d.tipo)} ${escapeHtml(d.numero)}</strong> • ${formatCurrency(d.valor)} (${escapeHtml(d.data)})<br/>
                  <span style="color:var(--gm-text-secondary); font-size:11px;">${escapeHtml(d.situacao)}</span>
                </div>
              `).join("") : `<div style="color:var(--gm-text-muted);">Nenhum documento listado nesta base.</div>`}
            </div>
          </div>

          <!-- COLUNA 3: DADOS DE CADASTRO, CONTATO E PRIMEIRA COMPRA -->
          <div class="detail-box">
            <div class="detail-box-title">
              <span>Cadastro & Contato Comercial</span>
            </div>
            <div style="display:flex; flex-direction:column; gap:4px;">
              <div><strong>Nome Fantasia:</strong> ${escapeHtml(c.nome_fantasia || c.nome)}</div>
              <div><strong>Contato:</strong> ${escapeHtml(c.contato_nome || "Não informado")}</div>
              <div><strong>Telefone:</strong> ${escapeHtml(c.telefone || "Indisponível")}</div>
              <div><strong>Data de cadastro:</strong> ${escapeHtml(c.data_cadastro || "Indisponível")}</div>
              <div><strong>1ª compra confirmada:</strong> ${escapeHtml(c.primeira_compra_data || "Indisponível")}</div>
              <div><strong>Compra nos últimos 2m cal.:</strong> ${c.comprou_ultimos_2m_calendario ? "Sim" : "Não"}</div>
            </div>
          </div>
        </div>
      `;
    }

    function renderClientsTableMode(items) {
      return `
        <div class="data-table-wrapper">
          <table class="clean-table" aria-label="Tabela da carteira geral de clientes">
            <thead>
              <tr>
                <th>Código</th>
                <th>Cliente</th>
                <th>Curva</th>
                <th>Responsável</th>
                <th>Situação / Motivo</th>
                <th>Compra no Mês</th>
                <th>Média (12m)</th>
                <th>Última Compra</th>
                <th>Ação</th>
              </tr>
            </thead>
            <tbody>
              ${items.map(c => `
                <tr>
                  <td><code>#${escapeHtml(c.codigo)}</code></td>
                  <td><strong>${escapeHtml(c.nome)}</strong></td>
                  <td><span class="curve-badge curve-${escapeHtml(c.curva)}">${escapeHtml(c.curva)}</span></td>
                  <td>${escapeHtml(c.vendedora_nome)}</td>
                  <td>${escapeHtml(c.motivo_comercial || (c.comprou_mes ? "Comprou no mês" : "Ainda não comprou"))}</td>
                  <td style="font-weight:700; color:${c.compra_mes <= 0 ? "var(--sem-red-text)" : "var(--gm-text)"};">
                    ${formatCurrency(c.compra_mes)}${c.comprou_mes?"":" • Sem compra"}
                  </td>
                  <td>${formatCurrency(c.media_mensal)}</td>
                  <td>${escapeHtml(c.ultima_compra_data)} (${c.dias_sem_comprar !== null ? `${c.dias_sem_comprar}d` : "s/ 12m"})</td>
                  <td>
                    <button type="button" class="btn btn-xs btn-whatsapp" data-whatsapp-client="${escapeHtml(c.codigo)}" ${!c.whatsapp?"disabled":""}>WhatsApp</button>
                  </td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      `;
    }

    /*************************************************************************
     * 7. VISÕES DE SUPERVISÃO E GESTÃO (TABELAS COMPARATIVAS, METAS, EQUIPE, ACESSOS)
     *************************************************************************/
    function renderCronosReconciliationCard(p) {
      if(!p.raw.financeiroGeral)return '';
      return `<section class="surface-card" style="margin-bottom:12px"><div class="card-header-row"><span class="section-title">Relatório financeiro geral</span></div>
        <p>Total geral do relatório salvo: <strong>${RadarContrato.moedaExata(p.raw.financeiroGeralExato?.receita)}</strong>.</p>
        <p class="hint">Inclui movimentações de responsáveis fora da seleção da equipe. A conferência completa com quatro casas decimais e o CSV estão no final da página.</p></section>`;
    }
    

    function renderComparativePerformanceTable(p, compactMode = false) {
      let lista = (p.vendedores_equipe || []).filter(v => v.participa_radar);
      if (p.usuario.perfil === "gestao" && STATE.selectedTeamSupervisor !== "TODOS") {
        lista = lista.filter(v => v.id_equipe === STATE.selectedTeamSupervisor);
      }

      return `
        <section class="surface-card" style="margin-bottom:12px;" aria-label="Desempenho comparativo individual da equipe">
          <div class="card-header-row">
            <div>
              <span class="section-title">Desempenho Comparativo Individual por Vendedora</span>
              <span style="font-size:11.5px; color:var(--gm-text-muted); margin-left:8px;">
                Abra uma vendedora para consultar sua carteira
              </span>
            </div>
          </div>

          <div class="data-table-wrapper">
            <table class="clean-table">
              <thead>
                <tr>
                  <th>Vendedora</th>
                  <th>Supervisor</th>
                  <th>Realizado</th>
                  <th>Meta Mensal</th>
                  <th>% Meta</th>
                  <th>Rentab.</th>
                  <th>Cobertura Carteira</th>
                  <th>Prioridades</th>
                  <th>Cad. Mês</th>
                  <th>Abertos (Orç/PV)</th>
                  <th>Ação Rápida</th>
                </tr>
              </thead>
              <tbody>
                ${lista.map(v => {
                  const temMeta = Number(v.meta || 0) > 0;
                  const pctMeta = temMeta && v.realizado!=null ? (v.realizado/v.meta)*100 : null;
                  const cobPct = v.clientes_carteira > 0 ? (v.compraram_mes / v.clientes_carteira) * 100 : 0;
                  return `
                    <tr>
                      <td><strong>${escapeHtml(v.nome)}</strong> <span class="client-code">#${escapeHtml(v.codigo)}</span></td>
                      <td>${escapeHtml(v.supervisor)}</td>
                      <td><strong>${formatCurrency(v.realizado)}</strong></td>
                      <td>${temMeta ? formatCurrency(v.meta) : `<span style="color:var(--gm-text-muted);">Meta não definida</span>`}</td>
                      <td>
                        ${pctMeta!=null ? `<span class="meta-status-pill ${pctMeta >= 100 ? "pill-green" : (pctMeta >= 70 ? "pill-amber" : "pill-red")}">${formatPercent(pctMeta, 1)}</span>` : "-"}
                      </td>
                      <td>${v.rentabilidade !== null ? formatPercent(v.rentabilidade, 1) : "Indisponível"}</td>
                      <td>${v.compraram_mes}/${v.clientes_carteira} (${formatPercent(cobPct, 0)})</td>
                      <td><strong style="color:var(--sem-red-text);">${v.prioridades}</strong></td>
                      <td>${v.cadastros_mes??"—"}</td>
                      <td>${v.orcamentos_abertos??"—"} orç. / ${v.prevendas_abertas??"—"} pv.</td>
                      <td>
                        <button type="button" class="btn btn-xs btn-blue" data-open-vendedora="${escapeHtml(v.codigo)}">
                          Abrir visão →
                        </button>
                      </td>
                    </tr>
                  `;
                }).join("")}
              </tbody>
            </table>
          </div>
        </section>
      `;
    }

    function renderMetasMensaisTab(p) {
      const mes=STATE.metaCompetencia||p.raw.competencia;
      return `<section class="surface-card"><div class="card-header-row"><span class="section-title">Metas mensais</span>
        <label>Mês <select id="selMetaCompetencia" class="select-filter">${p.raw.mesesMetas.map(m=>`<option value="${escapeHtml(m)}" ${mes===m?'selected':''}>${escapeHtml(m)}</option>`).join('')}</select></label></div>
        <div class="data-table-wrapper" data-draft-scope="metas_${escapeHtml(mes)}"><table class="clean-table"><thead><tr><th>Vendedora</th><th>Supervisor</th><th>Realizado</th><th>Meta (R$)</th><th>Ação</th></tr></thead><tbody>
        ${p.vendedores_equipe.map(v=>{const f=p.raw.financeiro[`1|${v.codigo}|${mes}`]||{};
          return `<tr><td><strong>${escapeHtml(v.nome)}</strong> (${escapeHtml(v.codigo)})</td><td>${escapeHtml(v.supervisor)}</td><td>${formatCurrency(f.RealizadoMeta)}</td>
            <td><label class="sr-only" for="inputMeta_${escapeHtml(v.codigo)}">Meta de ${escapeHtml(v.nome)}</label><input type="text" inputmode="decimal" class="input-search" id="inputMeta_${escapeHtml(v.codigo)}" value="${f.MetaValor!=null?Number(f.MetaValor).toFixed(2).replace('.',','):''}" placeholder="35.000,00" data-meta-input="${escapeHtml(v.codigo)}"><small class="hint">Registrada: ${f.MetaValor!=null?formatCurrency(f.MetaValor):"Não definida"}</small></td>
            <td><button type="button" class="btn btn-xs btn-primary" data-save-meta="${escapeHtml(v.codigo)}" ${STATE.pendingAction?'disabled':''}>Salvar meta</button></td></tr>`;}).join('')}
        </tbody></table></div><p class="hint">A supervisão altera apenas as metas de sua equipe. Duas alterações no mesmo valor exigem conferir a versão mais recente.</p></section>`;
    }
    

    function renderOpenDocumentsTab(p) {
      const orcs = p.orcamentos_abertos_lista || [];
      const pvs = p.prevendas_abertas_lista || [];
      return `
        <div class="docs-grid">
          <section class="surface-card">
            <div class="card-header-row">
              <span class="section-title">Orçamentos em Aberto (${p.documentosDisponiveis.orcamentos?orcs.length:"Indisponível"})</span>
              <span style="font-size:11.5px; color:var(--gm-text-muted);">Separados do faturamento realizado</span>
            </div>
            <div class="data-table-wrapper">
              <table class="clean-table">
                <thead>
                  <tr><th>Nº</th><th>Data</th><th>Cliente</th><th>Vendedora</th><th>Valor</th><th>Situação</th></tr>
                </thead>
                <tbody>
                  ${orcs.map(o => `
                    <tr>
                      <td><strong>${escapeHtml(o.numero)}</strong></td>
                      <td>${escapeHtml(o.data)}</td>
                      <td>${escapeHtml(o.cliente_nome)} (#${escapeHtml(o.cliente_codigo)})</td>
                      <td>${escapeHtml(o.vendedora)}</td>
                      <td><strong>${formatCurrency(o.valor)}</strong></td>
                      <td>${escapeHtml(o.situacao)}</td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          </section>

          <section class="surface-card">
            <div class="card-header-row">
              <span class="section-title">Pré-vendas em Aberto (${p.documentosDisponiveis.prevendas?pvs.length:"Indisponível"})</span>
              <span style="font-size:11.5px; color:var(--gm-text-muted);">Separadas do faturamento realizado</span>
            </div>
            <div class="data-table-wrapper">
              <table class="clean-table">
                <thead>
                  <tr><th>Nº</th><th>Data</th><th>Cliente</th><th>Vendedora</th><th>Valor</th><th>Situação</th></tr>
                </thead>
                <tbody>
                  ${pvs.map(pv => `
                    <tr>
                      <td><strong>${escapeHtml(pv.numero)}</strong></td>
                      <td>${escapeHtml(pv.data)}</td>
                      <td>${escapeHtml(pv.cliente_nome)} (#${escapeHtml(pv.cliente_codigo)})</td>
                      <td>${escapeHtml(pv.vendedora)}</td>
                      <td><strong>${formatCurrency(pv.valor)}</strong></td>
                      <td>${escapeHtml(pv.situacao)}</td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      `;
    }

    function renderCadastrosForaCarteiraTab(p) {
      const lista = p.cadastros_fora_carteira || [];
      return `
        <section class="surface-card" aria-label="Cadastros do mês fora da carteira ativa">
          <div class="card-header-row">
            <span class="section-title">Cadastros do Mês Fora da Carteira Ativa (${p.raw.cadastrosForaCarteiraCompletos?lista.length:`lista parcial: ${lista.length}`})</span>
            <span style="font-size:12px; color:var(--gm-text-secondary);">Clientes cadastrados no mês atribuídos a códigos fora da equipe ativa do Radar</span>
          </div>
          <div class="data-table-wrapper">
            <table class="clean-table">
              <thead>
                <tr><th>Código</th><th>Nome / Razão Social</th><th>Data de Cadastro</th><th>Responsável Registrado</th><th>Situação</th></tr>
              </thead>
              <tbody>
                ${lista.map(item => `
                  <tr>
                    <td><code>#${escapeHtml(item.codigo)}</code></td>
                    <td><strong>${escapeHtml(item.nome)}</strong></td>
                    <td>${escapeHtml(item.data_cadastro)}</td>
                    <td>${escapeHtml(item.responsavel)}</td>
                    <td>${escapeHtml(item.situacao)}</td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </section>
      `;
    }

    function renderEquipeDoRadarTab(p) {
      const q = STATE.equipeSearch.trim().toLowerCase();
      const todosNomes = (p.raw.equipe?.pessoas||[]).map(x=>({codigo:x.codigo,nome:x.nome,supervisor:x.supervisor,
        situacao_cadastral:x.inativo==='S'?'Inativo no Cronos':x.inativo==='N'?'Ativo':'Não informado na base',participa_radar:x.incluida,
        realizado:p.vendedores_equipe.find(v=>v.codigo===x.codigo)?.realizado??null})).filter(v =>
        !q ||
        String(v.nome).toLowerCase().includes(q) ||
        String(v.codigo).toLowerCase().includes(q) ||
        String(v.supervisor).toLowerCase().includes(q)
      );

      return `
        <section class="surface-card" aria-label="Administração da Equipe do Radar">
          <div class="card-header-row">
            <div>
              <span class="section-title">Equipe do Radar (Nomes Disponíveis no Cache)</span>
              <p style="font-size:12px; color:var(--gm-text-secondary); margin-top:2px;">
                A Gestão decide a participação. Faturamento zero não significa desligamento. Excluir da equipe preserva histórico financeiro e conta de acesso.
              </p>
            </div>
            <div style="display:flex; gap:8px; align-items:center;">
              <input
                type="search"
                id="inputEquipeSearch"
                class="input-search"
                style="width:220px;"
                placeholder="Buscar nome, código ou supervisor..."
                value="${escapeHtml(STATE.equipeSearch)}"
              />
              <button type="button" class="btn btn-primary" id="btnIncluirTodosEquipe" ${STATE.pendingAction ? "disabled" : ""}>
                Incluir todos os nomes
              </button>
            </div>
          </div>

          <div class="data-table-wrapper">
            <table class="clean-table">
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Nome no Cache</th>
                  <th>Supervisor</th>
                  <th>Situação Cadastral</th>
                  <th>Faturamento Mês</th>
                  <th>Participação no Radar</th>
                  <th>Ação</th>
                </tr>
              </thead>
              <tbody>
                ${todosNomes.map(v => `
                  <tr>
                    <td><code>#${escapeHtml(v.codigo)}</code></td>
                    <td><strong>${escapeHtml(v.nome)}</strong></td>
                    <td>${escapeHtml(v.supervisor || "Sem supervisor")}</td>
                    <td>
                      <span class="meta-status-pill ${v.situacao_cadastral === "Ativo" ? "pill-green" : "pill-neutral"}">
                        ${escapeHtml(v.situacao_cadastral)}
                      </span>
                    </td>
                    <td>${formatCurrency(v.realizado)}</td>
                    <td>
                      <span class="meta-status-pill ${v.participa_radar ? "pill-green" : "pill-amber"}">
                        ${v.participa_radar ? "Participando do Radar" : "Fora da equipe do Radar"}
                      </span>
                    </td>
                    <td>
                      ${v.participa_radar ? `
                        <button type="button" class="btn btn-xs" data-equipe-toggle="${escapeHtml(v.codigo)}" data-participar="false" ${STATE.pendingAction ? "disabled" : ""}>
                          Excluir do Radar
                        </button>
                      ` : `
                        <button type="button" class="btn btn-xs btn-blue" data-equipe-toggle="${escapeHtml(v.codigo)}" data-participar="true" ${STATE.pendingAction ? "disabled" : ""}>
                          Reincluir no Radar
                        </button>
                      `}
                    </td>
                  </tr>
                `).join("")}
              </tbody>
            </table>
          </div>
        </section>
      `;
    }

    function renderPerfisEAcessosTab(p) {return RadarAcessos.render(p);}
    

    /*************************************************************************
     * 8. MODAIS (WHATSAPP EDITÁVEL, ORÇAMENTOS/PRÉ-VENDAS, DIAGNÓSTICO, MAPA DE ARQUITETURA)
     *************************************************************************/
    function renderActiveModal() {
      const container = document.getElementById("modalContainer");
      if (!container) return;
      if (!STATE.activeModal) {
        container.innerHTML = "";
        return;
      }

      const m = STATE.activeModal;

      if (m.type === "whatsapp") {
        const c = m.data;
        const msgSugerida = `Olá, ${c.contato_nome || c.nome_fantasia || c.nome}! Tudo bem? Aqui é ${STATE.payload.usuario.nome}, da GM Limpezas.\n\nEstou passando para conferir a reposição de materiais de limpeza deste mês (${STATE.payload.mes_referencia}). ${c.produtos_habituais && c.produtos_habituais.length ? `Vi que costumam utilizar ${c.produtos_habituais.slice(0, 2).join(" e ")}.` : ""} Posso preparar uma cotação atualizada para vocês?`;
        const foneLimpo=c.whatsapp;
        return (container.innerHTML = `
          <div class="modal-backdrop" role="dialog" aria-modal="true" aria-label="Contato via WhatsApp">
            <div class="modal-card">
              <div class="modal-header">
                <h3>💬 Contato Comercial via WhatsApp • ${escapeHtml(c.nome_fantasia || c.nome)}</h3>
                <button type="button" class="btn-header" data-close-modal="true">✕</button>
              </div>
              <div class="modal-body">
                <div style="font-size:12.5px; color:var(--gm-text-secondary);">
                  <strong>Cliente:</strong> ${escapeHtml(c.nome)} (#${escapeHtml(c.codigo)})<br/>
                  <strong>Contato:</strong> ${escapeHtml(c.contato_nome || "Não cadastrado")} • <strong>Telefone:</strong> ${escapeHtml(c.telefone || "Indisponível")}<br/>
                  <strong>Contexto:</strong> ${escapeHtml(c.motivo_comercial || "Acompanhamento de carteira")}
                </div>
                <div class="filter-field">
                  <label for="txtWhatsappMessage">Mensagem sugerida (editável antes do envio humano)</label>
                  <textarea id="txtWhatsappMessage" rows="5" class="input-search" style="padding:8px; font-family:inherit;">${escapeHtml(msgSugerida)}</textarea>
                </div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn" data-close-modal="true">Cancelar</button>
                <button type="button" class="btn btn-whatsapp" id="btnSendHumanWhatsapp" data-phone="${escapeHtml(foneLimpo)}" ${!foneLimpo?"disabled":""}>
                  Revisar no WhatsApp →
                </button>
              </div>
            </div>
          </div>
        `);
      }

      if (m.type === "orcamentos" || m.type === "prevendas") {
        const isOrc = m.type === "orcamentos";
        const view=RadarContrato.escopo(STATE.payload,STATE);
        const lista=isOrc?view.orcamentos_abertos_lista:view.prevendas_abertas_lista;
        const disponivel=isOrc?view.documentosDisponiveis.orcamentos:view.documentosDisponiveis.prevendas;
        return (container.innerHTML = `
          <div class="modal-backdrop" role="dialog" aria-modal="true">
            <div class="modal-card modal-lg">
              <div class="modal-header">
                <h3>${isOrc ? "📋 Orçamentos em Aberto" : "📦 Pré-vendas em Aberto"} (${disponivel?lista.length:"Indisponível"})</h3>
                <button type="button" class="btn-header" data-close-modal="true">✕</button>
              </div>
              <div class="modal-body">
                <p style="font-size:12.5px; color:var(--gm-text-secondary);">
                  ${disponivel?"Documentos em aberto da última atualização. Não compõem o faturamento realizado até serem faturados no Cronos.":"Consulta indisponível no cache atual. Não é possível confirmar a quantidade de documentos."}
                </p>
                <div class="data-table-wrapper">
                  <table class="clean-table">
                    <thead>
                      <tr><th>Número</th><th>Data</th><th>Cliente</th><th>Vendedora</th><th>Valor</th><th>Situação</th></tr>
                    </thead>
                    <tbody>
                      ${lista.map(item => `
                        <tr>
                          <td><strong>${escapeHtml(item.numero)}</strong></td>
                          <td>${escapeHtml(item.data)}</td>
                          <td>${escapeHtml(item.cliente_nome)} (#${escapeHtml(item.cliente_codigo)})</td>
                          <td>${escapeHtml(item.vendedora)}</td>
                          <td><strong>${formatCurrency(item.valor)}</strong></td>
                          <td>${escapeHtml(item.situacao)}</td>
                        </tr>
                      `).join("")}
                    </tbody>
                  </table>
                </div>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn btn-primary" data-close-modal="true">Fechar consulta</button>
              </div>
            </div>
          </div>
        `);
      }

      if (m.type === "diagnostico") {
        const p = STATE.payload;
        return (container.innerHTML = `
          <div class="modal-backdrop" role="dialog" aria-modal="true">
            <div class="modal-card">
              <div class="modal-header">
                <h3>Diagnóstico Técnico, Ambiente e Base de Dados</h3>
                <button type="button" class="btn-header" data-close-modal="true">✕</button>
              </div>
              <div class="modal-body">
                <table class="clean-table">
                  <tbody>
                    <tr><th>Versão de referência</th><td><code>${escapeHtml(p.versao || "2026.10.21-r2")}</code></td></tr>
                    <tr><th>Ambiente de execução</th><td><code>${escapeHtml(p.ambiente || "PRODUCAO_STREAMLIT")}</code></td></tr>
                    <tr><th>Identificador da Base / Cache</th><td><code>${escapeHtml(p.base_id || "cronos_local_cache")}</code></td></tr>
                    <tr><th>Última atualização da base</th><td><strong>${escapeHtml(p.atualizado_em)}</strong></td></tr>
                    <tr><th>Abertura desta página (America/Sao_Paulo)</th><td>${escapeHtml(STATE.pageOpenedAt)}</td></tr>
                    <tr><th>Janela da carteira ativa</th><td>${escapeHtml(p.periodo_carteira_12m)}</td></tr>
                  </tbody>
                </table>
              </div>
              <div class="modal-footer">
                <button type="button" class="btn" data-trigger="reler_acessos">↻ Reler arquivos locais</button>
                <button type="button" class="btn btn-primary" data-close-modal="true">Fechar</button>
              </div>
            </div>
          </div>
        `);
      }

      }
    

    /*************************************************************************
     * 9. BINDING DE EVENTOS E INTERAÇÕES (COM DEBOUNCE NA BUSCA)
     *************************************************************************/
    let searchDebounceTimer = null;

    function bindInteractiveEvents() {
      // Botões de cabeçalho e diagnóstico
      const btnDiag = document.getElementById("btnOpenDiagnostico");
      if (btnDiag) btnDiag.onclick = () => { abrirModal({type:"diagnostico"}); };

      const btnSair = document.getElementById("btnSairRadar");
      if (btnSair) btnSair.onclick = () => sendStreamlitEvent("sair_radar", {}, "Encerrando sessão...");

      document.querySelectorAll('[data-trigger="reler_acessos"], #btnRelerArquivos').forEach(btn => {
        btn.onclick = () => sendStreamlitEvent(btn.id==="btnRelerArquivos"?"reler_arquivos":"reler_acessos",{},"Relendo arquivos locais...");
      });

      const btnDismissFb = document.getElementById("btnDismissFeedback");
      if (btnDismissFb) btnDismissFb.onclick = () => { STATE.lastFeedback = null; renderRadar(); };

      const btnClosePdf = document.getElementById("btnClosePdfBanner");
      if (btnClosePdf) btnClosePdf.onclick = () => { STATE.readyPdfFile = null; renderRadar(); };

      // Navegação por abas de Supervisão/Gestão
      document.querySelectorAll("[data-role-tab]").forEach(btn => {
        btn.onclick = () => {
          STATE.activeRoleTab = btn.getAttribute("data-role-tab");
          renderRadar();
        };
      });

      const selSup = document.getElementById("selFilterSupervisor");
      if (selSup) {
        selSup.onchange = (e) => {
          STATE.selectedTeamSupervisor = e.target.value;
          STATE.selectedVendedoraCodigo = "TODAS";
          STATE.currentPage = 1;
          renderRadar();
        };
      }

      const selVend = document.getElementById("selFilterVendedora");
      if (selVend) {
        selVend.onchange = (e) => {
          STATE.selectedVendedoraCodigo = e.target.value;
          STATE.currentPage = 1;
          renderRadar();
        };
      }

      const btnResetVend = document.getElementById("btnResetVendedoraScope");
      if (btnResetVend) {
        btnResetVend.onclick = () => {
          STATE.selectedVendedoraCodigo = "TODAS";
          STATE.currentPage = 1;
          renderRadar();
        };
      }

      // Abrir visão individual de uma vendedora com 1 clique na tabela comparativa
      document.querySelectorAll("[data-open-vendedora]").forEach(btn => {
        btn.onclick = () => {
          STATE.selectedVendedoraCodigo = btn.getAttribute("data-open-vendedora");
          STATE.activeRoleTab = "visao_geral";
          STATE.currentPage = 1;
          renderRadar();
          const ws = document.getElementById("clientsWorkspaceSection");
          if (ws) ws.scrollIntoView({ behavior: "smooth", block: "start" });
        };
      });

      // Caixas de resumo comercial (atalhos de recorte e modais de documentos)
      document.querySelectorAll("[data-quick-recorte]").forEach(btn => {
        btn.onclick = () => {
          STATE.activeRecorte = btn.getAttribute("data-quick-recorte");
          STATE.currentPage = 1;
          renderRadar();
          const ws = document.getElementById("clientsWorkspaceSection");
          if (ws) ws.scrollIntoView({ behavior: "smooth", block: "nearest" });
        };
      });

      const btnOrcModal = document.getElementById("btnOpenOrcamentosModal");
      if (btnOrcModal) btnOrcModal.onclick = () => { abrirModal({type:"orcamentos"}); };

      const btnPvModal = document.getElementById("btnOpenPrevendasModal");
      if (btnPvModal) btnPvModal.onclick = () => { abrirModal({type:"prevendas"}); };

      // Ações da Curva ABC (Toggles persistentes, filtros diretos e PDF pendentes)
      const btnAbcTable = document.getElementById("btnToggleAbcTable");
      if (btnAbcTable) btnAbcTable.onclick = () => { STATE.showAbcTextTable = !STATE.showAbcTextTable; renderRadar(); };

      const btnAbcInfo = document.getElementById("btnToggleAbcBaseInfo");
      if (btnAbcInfo) btnAbcInfo.onclick = () => { STATE.showAbcBaseInfo = !STATE.showAbcBaseInfo; renderRadar(); };

      document.querySelectorAll("[data-act-curve-all]").forEach(btn => {
        btn.onclick = () => {
          STATE.activeRecorte = "todos";
          STATE.filtroCurva = btn.getAttribute("data-act-curve-all");
          STATE.filtroSituacaoMes = "TODAS";
          STATE.currentPage = 1;
          renderRadar();
        };
      });

      document.querySelectorAll("[data-act-curve-missing]").forEach(btn => {
        btn.onclick = () => {
          STATE.activeRecorte = "todos";
          STATE.filtroCurva = btn.getAttribute("data-act-curve-missing");
          STATE.filtroSituacaoMes = "nao_comprou";
          STATE.currentPage = 1;
          renderRadar();
        };
      });

      document.querySelectorAll("[data-pdf-curva]").forEach(btn => {
        btn.onclick = () => {
          const curva = btn.getAttribute("data-pdf-curva");
          sendStreamlitEvent("pdf_pendentes", {
            curva: curva,
            codigo_vendedor: STATE.selectedVendedoraCodigo !== "TODAS" ? STATE.selectedVendedoraCodigo : STATE.payload.usuario.codigo_vendedor
          }, `Preparando PDF de pendentes (Curva ${curva})...`);
        };
      });

      // Recortes de clientes e subfiltro de cadastros do mês
      document.querySelectorAll("[data-recorte]").forEach(btn => {
        btn.onclick = () => {
          STATE.activeRecorte = btn.getAttribute("data-recorte");
          STATE.currentPage = 1;
          renderRadar();
        };
      });

      document.querySelectorAll("[data-sub-cad]").forEach(btn => {
        btn.onclick = () => {
          STATE.subFiltroCadastrosMes = btn.getAttribute("data-sub-cad");
          STATE.currentPage = 1;
          renderRadar();
        };
      });

      // Alternância Cartões / Tabela e Exportação CSV
      document.querySelectorAll("[data-view-mode]").forEach(btn => {
        btn.onclick = () => {
          STATE.supervisaoViewMode = btn.getAttribute("data-view-mode");
          renderRadar();
        };
      });

      const btnExportCsv = document.getElementById("btnExportFilteredCsv");
      if (btnExportCsv) {
        btnExportCsv.onclick = () => {
          const { list } = getFilteredAndSortedClients();
          const headers = ["Codigo", "Cliente", "Curva", "Responsavel", "Compra_Mes", "Media_12m", "Ultima_Compra", "Dias_Sem_Comprar"];
          const csvCell=v=>`"${String(v??"").replace(/^[=+@-]/,"' $&").replace(/"/g,'""')}"`;
          const rows = list.map(c => [
            c.codigo, c.nome, c.curva, c.vendedora_nome,
            c.compra_mes, c.media_mensal, c.ultima_compra_data, c.dias_sem_comprar ?? ""
          ].map(csvCell).join(";"));
          const blob = new Blob(["\uFEFF" + headers.join(";") + "\n" + rows.join("\n")], { type: "text/csv;charset=utf-8;" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = `carteira_filtrada_radar_${Date.now()}.csv`;
          a.click();
          URL.revokeObjectURL(url);
        };
      }

      // Busca com pequena espera (debounce 180ms) preservando cursor e foco
      const inpSearch = document.getElementById("inputClientSearch");
      if (inpSearch) {
        inpSearch.oninput = (e) => {
          STATE.searchQuery = e.target.value;
          STATE.currentPage = 1;
          clearTimeout(searchDebounceTimer);
          searchDebounceTimer = setTimeout(() => {
            renderRadar();
          }, 180);
        };
      }

      // Selects de filtros primários e avançados
      const bindSelectFilter = (id, stateKey) => {
        const el = document.getElementById(id);
        if (el) {
          el.onchange = (e) => {
            STATE[stateKey] = e.target.value;
            STATE.currentPage = 1;
            renderRadar();
          };
        }
      };

      bindSelectFilter("selFiltroCurva", "filtroCurva");
      bindSelectFilter("selFiltroSituacaoMes", "filtroSituacaoMes");
      bindSelectFilter("selOrdenacao", "ordenacao");
      bindSelectFilter("selDoisMesesCal", "filtroDoisMesesCal");
      bindSelectFilter("selPeriodoUltima", "filtroPeriodoUltima");
      bindSelectFilter("selDiasSemComprar", "filtroDiasSemComprar");
      bindSelectFilter("selFaixaMedia", "filtroFaixaMedia");
      bindSelectFilter("selValorUltima", "filtroValorUltima");
      bindSelectFilter("selDifMedia", "filtroDifMedia");

      const btnMoreFilters = document.getElementById("btnToggleMoreFilters");
      if (btnMoreFilters) {
        btnMoreFilters.onclick = () => {
          STATE.showMoreFilters = !STATE.showMoreFilters;
          renderRadar();
        };
      }

      // Remover chip individual ou limpar todos os filtros
      document.querySelectorAll("[data-remove-chip]").forEach(btn => {
        btn.onclick = () => {
          const k = btn.getAttribute("data-remove-chip");
          const resetVal = btn.getAttribute("data-reset-val");
          STATE[k] = resetVal;
          STATE.currentPage = 1;
          renderRadar();
        };
      });

      const btnClearAll = document.getElementById("btnClearAllFilters");
      if (btnClearAll) btnClearAll.onclick = clearAllClientFilters;

      const btnEmptyReset = document.getElementById("btnEmptyResetFilters");
      if (btnEmptyReset) btnEmptyReset.onclick = clearAllClientFilters;

      // Expansão persistente de detalhes do card de cliente
      document.querySelectorAll("[data-toggle-details]").forEach(btn => {
        btn.onclick = () => {
          const code = String(btn.getAttribute("data-toggle-details"));
          if (STATE.expandedClientCodes.has(code)) {
            STATE.expandedClientCodes.delete(code);
          } else {
            STATE.expandedClientCodes.add(code);
          }
          renderRadar();
        };
      });

      // Abertura do modal de WhatsApp com mensagem editável
      document.querySelectorAll("[data-whatsapp-client]").forEach(btn => {
        btn.onclick = () => {
          const code = String(btn.getAttribute("data-whatsapp-client"));
          const allLists = [...(STATE.payload.clientes || []), ...(STATE.payload.cadastros_mes_lista || [])];
          const client = allLists.find(c => String(c.codigo) === code);
          if (client) {
            STATE.activeModal = { type: "whatsapp", data: client };
            renderActiveModal();
            bindModalEvents();
            posicionarModal();
          }
        };
      });

      // Paginação
      const btnPrev = document.getElementById("btnPrevPage");
      if (btnPrev) btnPrev.onclick = () => { if (STATE.currentPage > 1) { STATE.currentPage--; renderRadar(); } };

      const btnNext = document.getElementById("btnNextPage");
      if (btnNext) btnNext.onclick = () => { STATE.currentPage++; renderRadar(); };

      // Eventos de Metas Mensais (salvar_meta)
      document.querySelectorAll("[data-save-meta]").forEach(btn => {
        btn.onclick = () => {
          const cod = btn.getAttribute("data-save-meta");
          const inp = document.getElementById(`inputMeta_${cod}`);
          const val=inp?inp.value:"";
          sendStreamlitEvent("salvar_meta", {
            codigo_vendedor: cod,
            valor_meta: val,
            mes_referencia: STATE.payload.mes_referencia
          }, `Salvando meta da vendedora #${cod}...`);
        };
      });

      // Eventos de Equipe do Radar (gerir_equipe)
      const inpEquipe = document.getElementById("inputEquipeSearch");
      if (inpEquipe) {
        inpEquipe.oninput = (e) => {
          STATE.equipeSearch = e.target.value;
          renderRadar();
        };
      }

      const btnIncTodos = document.getElementById("btnIncluirTodosEquipe");
      if (btnIncTodos) {
        btnIncTodos.onclick = () => {
          sendStreamlitEvent("gerir_equipe", { acao: "incluir_todos" }, "Incluindo todos os nomes na equipe do Radar...");
        };
      }

      document.querySelectorAll("[data-equipe-toggle]").forEach(btn => {
        btn.onclick = () => {
          const cod = btn.getAttribute("data-equipe-toggle");
          const part = btn.getAttribute("data-participar") === "true";
          sendStreamlitEvent("gerir_equipe", {
            acao: part ? "reincluir" : "excluir",
            codigo_vendedor: cod,
            participar: part
          }, `${part ? "Reincluindo" : "Excluindo"} código #${cod} na Equipe do Radar...`);
        };
      });

      // Gestão de acessos usa o mesmo contrato e identificador das ações Python.
      RadarAcessos.bind();
      const mesMeta=document.getElementById('selMetaCompetencia');
      if(mesMeta)mesMeta.onchange=()=>{STATE.metaCompetencia=mesMeta.value;renderRadar();};
      

    bindModalEvents();
    }

    function bindModalEvents() {
      document.querySelectorAll('[data-close-modal="true"]').forEach(btn => {
        btn.onclick = () => {
          STATE.activeModal = null;
          renderActiveModal();
        };
      });

      const btnSendWa = document.getElementById("btnSendHumanWhatsapp");
      if (btnSendWa) {
        btnSendWa.onclick = () => {
          const phone = btnSendWa.getAttribute("data-phone");
          const txtEl = document.getElementById("txtWhatsappMessage");
          const msg = txtEl ? txtEl.value : "";
          if(!/^55\d{2}9\d{8}$/.test(phone))return;
          const url = `https://wa.me/${phone}?text=${encodeURIComponent(msg)}`;
          window.open(url, "_blank", "noopener,noreferrer");
          STATE.activeModal = null;
          renderActiveModal();
        };
      }
    }

    /*************************************************************************
     * 10. INICIALIZAÇÃO DO COMPONENTE E CONTROLES DE DEMONSTRAÇÃO DO CANVAS
     *************************************************************************/
    function posicionarModal() {
      const backdrop=document.querySelector('.modal-backdrop');if(!backdrop)return;
      let y=window.scrollY;
      try {y=Math.max(0,window.parent.scrollY-window.frameElement.getBoundingClientRect().top-window.parent.scrollY);}catch(e){}
      backdrop.style.top=Math.max(8,y+24)+'px';
      backdrop.querySelector('button')?.focus({preventScroll:true});adjustStreamlitFrameHeight();
    }
    function abrirModal(modal) {STATE.activeModal=modal;renderActiveModal();bindModalEvents();posicionarModal();}
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&STATE.activeModal){STATE.activeModal=null;renderActiveModal();}});
    function bootstrapRadar() {
      renderRadar();
      new ResizeObserver(adjustStreamlitFrameHeight).observe(document.getElementById('radarAppRoot'));
      window.parent.postMessage({isStreamlitMessage:true,type:'streamlit:componentReady',apiVersion:1},'*');
    }
    

    document.addEventListener("DOMContentLoaded", bootstrapRadar);
