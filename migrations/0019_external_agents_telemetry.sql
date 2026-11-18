-- ============================================================================
-- Migration 0019: Central de Telemetria para Agentes Externos (O Outro Lado)
-- Catalogo completo (~89 agentes, bots, subagentes e gates), runs de pipeline,
-- execucoes individuais, eventos em tempo real (Realtime), tokens de ingestao,
-- RPC atomica de ingestao e views para o Studio UI.
-- ============================================================================

-- 1. Catalogo global de agentes externos
CREATE TABLE IF NOT EXISTS public.external_agent_catalog (
    agent_key        text PRIMARY KEY,
    display_name     text NOT NULL,
    group_key        text NOT NULL CHECK (
        group_key IN ('standalone','hsl_editorial','hsl_cinematic','hsl_media','hsl_postprod','shorts_cutter')
    ),
    sub_group        text NOT NULL,
    agent_kind       text NOT NULL CHECK (agent_kind IN ('agent','bot','subagent','gate','orchestrator')),
    source_path      text NOT NULL,
    runtime_lang     text NOT NULL CHECK (runtime_lang IN ('python','typescript','mixed')),
    studio_room_key  text NOT NULL REFERENCES public.studio_rooms(key),
    studio_agent_key text NOT NULL REFERENCES public.agent_definitions(key),
    pipeline_order   integer NOT NULL,
    description      text NOT NULL,
    active           boolean NOT NULL DEFAULT true
);

INSERT INTO public.external_agent_catalog (
    agent_key, display_name, group_key, sub_group, agent_kind,
    source_path, runtime_lang, studio_room_key, studio_agent_key, pipeline_order, description
) VALUES
    -- ------------------------------------------------------------------------
    -- 2. Agentes & Bots Standalone (AUTOMACAO - O OUTRO LADO/)
    -- ------------------------------------------------------------------------
    ('sound-agent', 'Sound Agent (Remotion AudioPlan)', 'standalone', 'Áudio & Empacotamento Standalone', 'agent',
     'AUTOMACAO - O OUTRO LADO/sound-agent/index.ts', 'typescript', 'gravacao', 'edicao', 10,
     'Analisa cenas (scene-analyzer), consulta RAG, seleciona SFX e trilhas, otimiza 3 bandas e gera AudioPlan + TSX Remotion.'),
    ('sfx-agent', 'SFX Agent (Banco de Efeitos)', 'standalone', 'Áudio & Empacotamento Standalone', 'agent',
     'AUTOMACAO - O OUTRO LADO/sfx-agent/sfxAgent.ts', 'typescript', 'gravacao', 'edicao', 20,
     'Constrói banco de efeitos sonoros (public/audio/sfx/), convertendo pacotes e sintetizando braams, booms, whooshes, tension e foley.'),
    ('music-agent', 'Music Agent (Banco Musical)', 'standalone', 'Áudio & Empacotamento Standalone', 'agent',
     'AUTOMACAO - O OUTRO LADO/music-agent/musicAgent.ts', 'typescript', 'gravacao', 'edicao', 30,
     'Constrói banco musical (public/audio/music/) por mood (epic, suspense, emotional, ambient, action) com 100 presets de estúdio.'),
    ('packaging-agent', 'Packaging Agent (PublicationPackagingSquad)', 'standalone', 'Áudio & Empacotamento Standalone', 'agent',
     'AUTOMACAO - O OUTRO LADO/packaging-agent/index.ts', 'typescript', 'estrategia_publicacao', 'publicacao', 40,
     'Gera pacote YouTube com ThumbnailPlanner (A/B/C), TitlePlanner sem repetição, DescriptionAndSeoPlanner e ThumbnailRenderer.'),
    ('firefly-automation', 'Firefly Automation (Orchestrator)', 'standalone', 'firefly-automation', 'orchestrator',
     'AUTOMACAO - O OUTRO LADO/firefly-automation/', 'python', 'gravacao', 'edicao', 50,
     'Automação Python/Patchright Chromium com fila SQLite WAL (CAS) para geração Image-to-Video no Adobe Firefly (Kling 3.0 / Veo 3.1 Fast).'),
    ('firefly-worker', 'Firefly Worker Execution Agent', 'standalone', 'firefly-automation', 'subagent',
     'AUTOMACAO - O OUTRO LADO/firefly-automation/worker.py', 'python', 'gravacao', 'edicao', 51,
     'Consome jobs atômicos via claim_job(), seleciona modelo/resolução/duração, sobe start frame, injeta prompt e baixa MP4.'),
    ('firefly-state-reader', 'Firefly StateReader Engine', 'standalone', 'firefly-automation', 'subagent',
     'AUTOMACAO - O OUTRO LADO/firefly-automation/state_reader.py', 'python', 'gravacao', 'edicao', 52,
     'Inspeciona o DOM do Adobe Firefly (LOGGED_OUT, CONTENT_REJECTED, QUOTA_EXHAUSTED, RESULT_READY, STILL_GENERATING).'),
    ('firefly-watchdog', 'Firefly Watchdog Guard Agent', 'standalone', 'firefly-automation', 'subagent',
     'AUTOMACAO - O OUTRO LADO/firefly-automation/watchdog.py', 'python', 'gravacao', 'edicao', 53,
     'Monitora travamentos por wall-clock (WATCHDOG_WALL_CLOCK) e reinicia contextos travados.'),
    ('firefly-jobstore', 'Firefly JobStore & Verification Subagent', 'standalone', 'firefly-automation', 'subagent',
     'AUTOMACAO - O OUTRO LADO/firefly-automation/MAPA_AGENTES_SUBAGENTES.md', 'python', 'sala_dados', 'dados', 54,
     'Coordena transações SQLite WAL (CAS) e validação automatizada via pytest.'),
    ('chatgpt-image-bot', 'ChatGPT Image Bot (Playwright)', 'standalone', 'Bots Web Automação', 'bot',
     'AUTOMACAO - O OUTRO LADO/chatgpt-image-bot/README.md', 'python', 'design_thumbnail', 'thumbnail', 60,
     'Automação Python/Playwright com perfil persistente (profile/) para gerar e baixar imagens via web ChatGPT sem API key.'),

    -- ------------------------------------------------------------------------
    -- 3. Pipeline HSL — Editorial, Pesquisa & RAG
    -- ------------------------------------------------------------------------
    ('ReferenceInsightIngestAgent', 'ReferenceInsightIngestAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'pesquisa', 'pesquisa', 100,
     'Ingere insights e métricas de vídeos de referência para alimentar o repositório editorial.'),
    ('AbrahamRagIngestAgent', 'AbrahamRagIngestAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'sala_dados', 'dados', 110,
     'Ingere princípios de estrutura narrativa e retenção (Abraham) na base vetorial/RAG.'),
    ('AbrahamRagRetrievalAgent', 'AbrahamRagRetrievalAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'pesquisa', 'pesquisa', 120,
     'Recupera princípios de engenharia de atenção e retenção da base Abraham sem vazar prosa-fonte.'),
    ('EugeneRagIngestAgent', 'EugeneRagIngestAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'sala_dados', 'dados', 130,
     'Ingere princípios de copywriting científico (Eugene Schwartz) na base RAG.'),
    ('EugeneRagRetrievalAgent', 'EugeneRagRetrievalAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'pesquisa', 'pesquisa', 140,
     'Recupera mecanismos de desejo, consciência e sofisticação de Eugene Schwartz sem vazar prosa-fonte.'),
    ('AudienceStrategyAgent', 'AudienceStrategyAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'estrategia', 150,
     'Define estratégia de audiência, nível de consciência e alinhamento editorial do episódio.'),
    ('EpisodeBriefAgent', 'EpisodeBriefAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'estrategia', 160,
     'Estrutura o briefing completo do episódio com restrições e objetivos.'),
    ('SystemsResearchAgent', 'SystemsResearchAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'pesquisa', 'pesquisa', 170,
     'Pesquisa fontes primárias, mecanismos técnicos e dados factuais verificáveis.'),
    ('ClaimRegistryAgent', 'ClaimRegistryAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'pesquisa', 'pesquisa', 180,
     'Registra e audita afirmações (claims) rastreáveis vinculadas a evidências e fontes.'),
    ('ThesisAgent', 'ThesisAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'estrategia', 190,
     'Formula a tese central do documentário e o diferencial argumentativo.'),
    ('CausalModelAgent', 'CausalModelAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'estrategia', 200,
     'Constrói o modelo causal ligando fatos, consequências e implicações da narrativa.'),
    ('AttentionArchitectureAgent', 'AttentionArchitectureAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'estrategia', 210,
     'Projeta a arquitetura de hook, open loops, escalada de tensão e payoff.'),
    ('DocumentaryScriptAgent', 'DocumentaryScriptAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'roteiro', 220,
     'Escreve o roteiro documental completo seguindo a voz do canal e a arquitetura de atenção.'),
    ('DocumentaryEditorAgent', 'DocumentaryEditorAgent', 'hsl_editorial', 'Editorial, Pesquisa & RAG', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'roteiro', 230,
     'Consolida o plano técnico documental, revisa cortes narrativos e prepara para direção visual.'),
    ('PhraseOriginalityGate', 'PhraseOriginalityGate', 'hsl_editorial', 'Gates Editoriais', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'roteiro', 240,
     'Gate determinístico que bloqueia sobreposição frasal ou plágio em relação às referências.'),
    ('EugeneRagOriginalityGate', 'EugeneRagOriginalityGate', 'hsl_editorial', 'Gates Editoriais', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'roteiro', 250,
     'Gate que garante que nenhuma prosa-fonte do RAG Eugene Schwartz vazou para o roteiro.'),
    ('PromiseDeliveryGate', 'PromiseDeliveryGate', 'hsl_editorial', 'Gates Editoriais', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'estrategia', 260,
     'Gate que valida se o roteiro entrega integralmente a promessa do título e do hook.'),
    ('OriginalitySafetyGate', 'OriginalitySafetyGate', 'hsl_editorial', 'Gates Editoriais', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'roteiro', 270,
     'Gate final de segurança e originalidade editorial antes da direção cinematográfica.'),

    -- ------------------------------------------------------------------------
    -- 3. Pipeline HSL — Direção Cinematográfica & Execução
    -- ------------------------------------------------------------------------
    ('NarrativeBeatDirectorAgent', 'NarrativeBeatDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'mesa_agentes', 'roteiro', 300,
     'Quebra o roteiro em narrative beats com 100% de cobertura temporal e semântica.'),
    ('CinematicShotDirectorAgent', 'CinematicShotDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 310,
     'Define enquadramento, lente, movimento de câmera e linguagem cinematográfica por shot.'),
    ('ContinuityDirectorAgent', 'ContinuityDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 320,
     'Valida continuidade visual, espacial, cromática e de sujeito entre cenas consecutivas.'),
    ('SceneChoreographyAgent', 'SceneChoreographyAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 330,
     'Distribui microeventos visuais dentro das cenas para evitar planos estáticos.'),
    ('EditRhythmDirectorAgent', 'EditRhythmDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 340,
     'Controla ritmo de edição, duração de cortes e WPM (palavras por minuto).'),
    ('TransitionDirectorAgent', 'TransitionDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 350,
     'Define transições motivadas entre beats e cenas (whip, match cut, L-cut, J-cut).'),
    ('RemotionChoreographyAgent', 'RemotionChoreographyAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 360,
     'Especifica cues, keyframes, overlays e animações determinísticas para o Remotion.'),
    ('KlingMotionDirectorAgent', 'KlingMotionDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 370,
     'Gera prompts de movimento e física de câmera otimizados para Kling 3.0.'),
    ('VisualShotDirectorAgent', 'VisualShotDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 380,
     'Orquestra composição visual e direção de arte de cada plano do episódio.'),
    ('CinematicCoverageDirectorAgent', 'CinematicCoverageDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/cinematicCoveragePolicy.ts', 'typescript', 'gravacao', 'edicao', 390,
     'Define política de cobertura e mix de shots (I2V, stock, motion graphics) por cena.'),
    ('MotionRouteDirectorAgent', 'MotionRouteDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 400,
     'Roteia cada shot entre motores (Kling 3.0, Veo 3.1 Fast, Remotion, Stock).'),
    ('VeoMotionDirectorAgent', 'VeoMotionDirectorAgent', 'hsl_cinematic', 'Direção Cinematográfica', 'agent',
     'hsl/cinematic/agents/generatedMotion.ts', 'typescript', 'gravacao', 'edicao', 410,
     'Gera prompts e especificações de áudio/movimento nativo para Veo 3.1 Fast.'),
    ('VisualCoverageQaAgent', 'VisualCoverageQaAgent', 'hsl_cinematic', 'Gates Cinematográficos', 'gate',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 420,
     'Gate que verifica se 100% da timeline possui cobertura visual sem buracos ou repetições.'),
    ('CinematicEditQaAgent', 'CinematicEditQaAgent', 'hsl_cinematic', 'Gates Cinematográficos', 'gate',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 430,
     'Gate que audita ritmo de cortes, WPM, transições e aderência à coreografia.'),
    ('VisualIdentityContractGate', 'VisualIdentityContractGate', 'hsl_cinematic', 'Gates Cinematográficos', 'gate',
     'hsl/cinematic/agents/ + executionAgents.ts', 'typescript', 'gravacao', 'edicao', 440,
     'Gate que bloqueia desvios da identidade visual oficial do canal O Outro Lado.'),

    -- ------------------------------------------------------------------------
    -- 3. Pipeline HSL — Mídia, Start Frames & Intake
    -- ------------------------------------------------------------------------
    ('WebFootageHarvesterAgent', 'WebFootageHarvesterAgent', 'hsl_media', 'Mídia, Start Frames & Intake', 'agent',
     'hsl/webFootageHarvesterAgent.ts', 'typescript', 'pesquisa', 'pesquisa', 500,
     'Busca e sanitiza footage em Pexels/Pixabay/OpenArchive com filtro estrito de procedência.'),
    ('WebFootageTrustGate', 'WebFootageTrustGate', 'hsl_media', 'Mídia, Start Frames & Intake', 'gate',
     'hsl/webFootageHarvesterAgent.ts', 'typescript', 'pesquisa', 'pesquisa', 510,
     'Gate de confiança e licenciamento contra scrapers arbitrários ou fontes não verificadas.'),
    ('PremiumMotionStartFrameAgent', 'PremiumMotionStartFrameAgent', 'hsl_media', 'Mídia, Start Frames & Intake', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'design_thumbnail', 'thumbnail', 520,
     'Empacota start frames com overlay-spec e motion-path-spec para geração I2V.'),
    ('StartFrameQaAgent', 'StartFrameQaAgent', 'hsl_media', 'Mídia, Start Frames & Intake', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'design_thumbnail', 'thumbnail', 530,
     'Gate que valida resolução, textura mínima e qualidade técnica dos start frames.'),
    ('StartFrameIdentityGate', 'StartFrameIdentityGate', 'hsl_media', 'Mídia, Start Frames & Intake', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'design_thumbnail', 'thumbnail', 540,
     'Gate que valida hash, lineage e fidelidade visual de identidade nos start frames.'),
    ('StartFrameContinuityAgent', 'StartFrameContinuityAgent', 'hsl_media', 'Mídia, Start Frames & Intake', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'design_thumbnail', 'thumbnail', 550,
     'Garante continuidade de paleta, iluminação e sujeito entre start frames adjacentes.'),

    -- ------------------------------------------------------------------------
    -- 3. Pipeline HSL — Pós-Produção, Áudio & Publicação
    -- ------------------------------------------------------------------------
    -- Voz
    ('NarrationVoiceAgent', 'NarrationVoiceAgent', 'hsl_postprod', 'Pós-Produção · Voz', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 600,
     'Sintetiza narração principal via ElevenLabs (voz Chris) em WAV 48 kHz.'),
    ('NarrationPerformanceAgent', 'NarrationPerformanceAgent', 'hsl_postprod', 'Pós-Produção · Voz', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 610,
     'Ajusta prosódia, pausas dramáticas, ênfases e cadência da narração.'),
    ('DialogLevelingAgent', 'DialogLevelingAgent', 'hsl_postprod', 'Pós-Produção · Voz', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 620,
     'Nivela diálogos e normaliza voz para -16 LUFS WAV 48 kHz.'),
    ('LoudnessQaAgent', 'LoudnessQaAgent', 'hsl_postprod', 'Pós-Produção · Voz', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 630,
     'Gate de auditoria de loudness (-16 LUFS, true peak, ausência de clipping).'),

    -- SFX/Áudio Nativo
    ('KenneySoundFxAssetAgent', 'KenneySoundFxAssetAgent', 'hsl_postprod', 'Pós-Produção · SFX & Áudio Nativo', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 640,
     'Seleciona e prepara ativos da cama sonora Kenney Sound FX.'),
    ('SoundFxDesignAgent', 'SoundFxDesignAgent', 'hsl_postprod', 'Pós-Produção · SFX & Áudio Nativo', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 650,
     'Projeta posicionamento de efeitos sonoros sincronizados aos beats visuais.'),
    ('SoundFxMixAgent', 'SoundFxMixAgent', 'hsl_postprod', 'Pós-Produção · SFX & Áudio Nativo', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 660,
     'Mixa trilhas, SFX e ducking dinâmico sob a narração.'),
    ('SoundFxQaAgent', 'SoundFxQaAgent', 'hsl_postprod', 'Pós-Produção · SFX & Áudio Nativo', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 670,
     'Gate de QA que valida sincronia de SFX, balanço espectral e ausência de mascaramento vocal.'),
    ('SoundDesignAgent', 'SoundDesignAgent', 'hsl_postprod', 'Pós-Produção · SFX & Áudio Nativo', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 680,
     'Define arquitetura global de sound design por ato do episódio.'),
    ('NativeGeneratedAudioAgent', 'NativeGeneratedAudioAgent', 'hsl_postprod', 'Pós-Produção · SFX & Áudio Nativo', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 690,
     'Extrai stems de áudio nativo gerados pelo Veo 3.1 Fast.'),
    ('HybridSoundBedAgent', 'HybridSoundBedAgent', 'hsl_postprod', 'Pós-Produção · SFX & Áudio Nativo', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 700,
     'Combina stems nativos do Veo 3.1 Fast com a cama de áudio Kenney.'),

    -- Render & QA
    ('LicensedAssetAgent', 'LicensedAssetAgent', 'hsl_postprod', 'Pós-Produção · Render & QA', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 710,
     'Verifica licenças, atribuições e integridade de todos os assets antes do render.'),
    ('RemotionAssemblyAgent', 'RemotionAssemblyAgent', 'hsl_postprod', 'Pós-Produção · Render & QA', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 720,
     'Monta e renderiza a composição final do episódio no Remotion.'),
    ('TypographyQaAgent', 'TypographyQaAgent', 'hsl_postprod', 'Pós-Produção · Render & QA', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 730,
     'Gate que audita legibilidade, contraste, safe areas e ortografia de tipografia em tela.'),
    ('MonetizationSafetyQaAgent', 'MonetizationSafetyQaAgent', 'hsl_postprod', 'Pós-Produção · Render & QA', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'estrategia_publicacao', 'publicacao', 740,
     'Gate de conformidade com diretrizes de monetização do YouTube e brand safety.'),
    ('FinalRenderQaAgent', 'FinalRenderQaAgent', 'hsl_postprod', 'Pós-Produção · Render & QA', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'gravacao', 'edicao', 750,
     'Gate final de renderização (codec, resolução, áudio, frames pretos, duração).'),

    -- Empacotamento
    ('TitlePackagingAgent', 'TitlePackagingAgent', 'hsl_postprod', 'Pós-Produção · Empacotamento', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'mesa_agentes', 'titulos', 760,
     'Gera e seleciona opções de título de alto CTR alinhadas ao ângulo do episódio.'),
    ('ThumbnailArtDirectorAgent', 'ThumbnailArtDirectorAgent', 'hsl_postprod', 'Pós-Produção · Empacotamento', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'design_thumbnail', 'thumbnail', 770,
     'Dirige conceito visual, contraste e hierarquia da thumbnail sem repetir texto do título.'),
    ('ThumbnailBaseFrameAgent', 'ThumbnailBaseFrameAgent', 'hsl_postprod', 'Pós-Produção · Empacotamento', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'design_thumbnail', 'thumbnail', 780,
     'Gera/seleciona o frame base de alta resolução para composição da capa.'),
    ('ThumbnailRenderAgent', 'ThumbnailRenderAgent', 'hsl_postprod', 'Pós-Produção · Empacotamento', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'design_thumbnail', 'thumbnail', 790,
     'Renderiza as variantes finais A/B/C da thumbnail.'),
    ('YouTubeMetadataAgent', 'YouTubeMetadataAgent', 'hsl_postprod', 'Pós-Produção · Empacotamento', 'agent',
     'hsl/ + docs/AGENTS.md', 'typescript', 'estrategia_publicacao', 'publicacao', 800,
     'Monta descrição SEO, capítulos, tags e metadados de publicação no YouTube.'),
    ('PublicationPackagingQaAgent', 'PublicationPackagingQaAgent', 'hsl_postprod', 'Pós-Produção · Empacotamento', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'estrategia_publicacao', 'publicacao', 810,
     'Gate de qualidade do pacote completo de publicação (título + capa + metadados).'),
    ('PromiseAlignmentGate', 'PromiseAlignmentGate', 'hsl_postprod', 'Pós-Produção · Empacotamento', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'estrategia_publicacao', 'publicacao', 820,
     'Gate que audita coerência entre thumbnail, título e entrega real dos primeiros 30s.'),
    ('ThumbnailTechnicalQaGate', 'ThumbnailTechnicalQaGate', 'hsl_postprod', 'Pós-Produção · Empacotamento', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'design_thumbnail', 'thumbnail', 830,
     'Gate técnico da capa (1280x720, peso < 2MB, contraste, legibilidade mobile).'),
    ('HumanSelectionGate', 'HumanSelectionGate', 'hsl_postprod', 'Pós-Produção · Empacotamento', 'gate',
     'hsl/ + docs/AGENTS.md', 'typescript', 'estrategia_publicacao', 'publicacao', 840,
     'Gate humano obrigatório para seleção final da variante e autorização de publicação.'),

    -- ------------------------------------------------------------------------
    -- 4. Squad de Cortes — Strategic Shorts Cutter (SHORTS - O OUTRO LADO/strategic_cutter/)
    -- ------------------------------------------------------------------------
    ('agent_00_orchestrator', 'SHORTS ORCHESTRATOR (agent_00)', 'shorts_cutter', 'Strategic Shorts Cutter', 'orchestrator',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_00_orchestrator.py', 'python', 'estrategia_publicacao', 'publicacao', 900,
     'Controla fluxo dos 14 agentes, transições de estado e Master Manifest.'),
    ('agent_01_ingest', 'MEDIA INGEST AGENT (agent_01)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_01_ingest.py', 'python', 'sala_dados', 'dados', 901,
     'Audita MP4 de entrada, valida codecs e extrai áudio 16 kHz mono para o Whisper.'),
    ('agent_02_transcription', 'TRANSCRIPTION AGENT (agent_02)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_02_transcription.py', 'python', 'sala_dados', 'dados', 902,
     'Transcreve palavra a palavra com faster-whisper (transcript.json e transcript.srt).'),
    ('agent_03_semantic_map', 'SEMANTIC VIDEO MAPPER (agent_03)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_03_semantic_map.py', 'python', 'pesquisa', 'pesquisa', 903,
     'Mapeia arcos narrativos e funções do vídeo (semantic_map.json).'),
    ('agent_04_moment_miner', 'MOMENT MINER (agent_04)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_04_moment_miner.py', 'python', 'mesa_agentes', 'estrategia', 904,
     'Minera candidatos nos 7 tipos (resultado inesperado, antes/depois, erro/falha, comparação, demo, tese física, procedimento).'),
    ('agent_05_payoff_hunter', 'PAYOFF HUNTER (agent_05)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_05_payoff_hunter.py', 'python', 'mesa_agentes', 'estrategia', 905,
     'Trabalha de trás para frente localizando o payoff narrativo e a janela mínima de contexto.'),
    ('agent_06_story_rebuilder', 'STORY REBUILDER (agent_06)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_06_story_rebuilder.py', 'python', 'mesa_agentes', 'roteiro', 906,
     'Reorganiza momentos/payoffs em micro-histórias GPC (Gancho → Progressão → Clímax).'),
    ('agent_07_hook_architect', 'HOOK ARCHITECT (agent_07)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_07_hook_architect.py', 'python', 'mesa_agentes', 'titulos', 907,
     'Cria 3 opções de gancho (Resultado, Problema, Curiosidade) via Colisão Mental + Regra de Schwartz.'),
    ('agent_08_clip_scorer', 'STRATEGIC CLIP SCORER (agent_08)', 'shorts_cutter', 'Strategic Shorts Cutter', 'gate',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_08_clip_scorer.py', 'python', 'mesa_agentes', 'estrategia', 908,
     'Pontua candidatos em 10 dimensões e aplica Hard Gates.'),
    ('agent_09_master_editor', 'MASTER SHORTS EDITOR (agent_09)', 'shorts_cutter', 'Strategic Shorts Cutter', 'gate',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_09_master_editor.py', 'python', 'mesa_agentes', 'roteiro', 909,
     'Veredito final fail-closed; converte aprovados em ShortEditTimeline (approved/short_XXX.json).'),
    ('agent_10_video_cutter', 'VIDEO CUTTER (agent_10)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_10_video_cutter.py', 'python', 'gravacao', 'edicao', 910,
     'Executa cortes frame-accurate via FFmpeg e concatena beats com continuidade de áudio.'),
    ('agent_11_vertical_director', 'VERTICAL FRAME DIRECTOR (agent_11)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_11_vertical_director.py', 'python', 'gravacao', 'edicao', 911,
     'Converte 16:9 para 9:16 Full-Bleed (1080x1920) sem letterbox e aplica legendas ASS.'),
    ('agent_12_caption_agent', 'CAPTION & EMPHASIS AGENT (agent_12)', 'shorts_cutter', 'Strategic Shorts Cutter', 'agent',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_12_caption_agent.py', 'python', 'design_thumbnail', 'thumbnail', 912,
     'Gera legendas animadas palavra a palavra em .ass na paleta oficial (#F4F4F0, #FF5500, #00F0FF, #060709).'),
    ('agent_13_final_qa', 'FINAL SHORT QA (agent_13)', 'shorts_cutter', 'Strategic Shorts Cutter', 'gate',
     'SHORTS - O OUTRO LADO/strategic_cutter/agent_13_final_qa.py', 'python', 'gravacao', 'edicao', 913,
     'Audita 1080x1920, H.264/AAC, frames pretos, >5MB, sincronismo e entrega de hook/payoff (qa/final_report.json).')
ON CONFLICT (agent_key) DO UPDATE
SET display_name     = EXCLUDED.display_name,
    group_key        = EXCLUDED.group_key,
    sub_group        = EXCLUDED.sub_group,
    agent_kind       = EXCLUDED.agent_kind,
    source_path      = EXCLUDED.source_path,
    runtime_lang     = EXCLUDED.runtime_lang,
    studio_room_key  = EXCLUDED.studio_room_key,
    studio_agent_key = EXCLUDED.studio_agent_key,
    pipeline_order   = EXCLUDED.pipeline_order,
    description      = EXCLUDED.description,
    active           = true;

-- 2. Execucoes de pipeline externas (episodio HSL, batch de Shorts, daemon bot)
CREATE TABLE IF NOT EXISTS public.external_pipeline_runs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id        uuid NOT NULL,
    content_item_id   uuid NULL,
    external_run_id   text NOT NULL CHECK (char_length(trim(external_run_id)) BETWEEN 2 AND 160),
    pipeline_kind     text NOT NULL DEFAULT 'custom' CHECK (
        pipeline_kind IN ('hsl_episode','shorts_cutter','standalone_bot','firefly_batch','audio_factory','custom')
    ),
    title             text NOT NULL CHECK (char_length(trim(title)) BETWEEN 1 AND 240),
    status            text NOT NULL DEFAULT 'running' CHECK (
        status IN ('queued','running','waiting_human','completed','failed','cancelled')
    ),
    current_agent_key text NULL REFERENCES public.external_agent_catalog(agent_key),
    progress          numeric(5,4) NULL CHECK (progress IS NULL OR (progress >= 0 AND progress <= 1)),
    total_agents      integer NULL CHECK (total_agents IS NULL OR total_agents >= 0),
    completed_agents  integer NOT NULL DEFAULT 0 CHECK (completed_agents >= 0),
    failed_agents     integer NOT NULL DEFAULT 0 CHECK (failed_agents >= 0),
    host_name         text NULL,
    source_repo       text NULL,
    metadata          jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
    finished_at       timestamptz NULL,
    created_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id),
    UNIQUE (channel_id, external_run_id),
    CONSTRAINT fk_ext_pipeline_runs_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_ext_pipeline_runs_item_ws
        FOREIGN KEY (workspace_id, content_item_id)
        REFERENCES public.content_items(workspace_id, id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ext_pipeline_runs_channel_updated
    ON public.external_pipeline_runs (workspace_id, channel_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ext_pipeline_runs_status
    ON public.external_pipeline_runs (channel_id, status, updated_at DESC);

CREATE TRIGGER trg_ext_pipeline_runs_updated_at
    BEFORE UPDATE ON public.external_pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 3. Execucao individual de cada agente externo
CREATE TABLE IF NOT EXISTS public.external_agent_executions (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id          uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id            uuid NOT NULL,
    pipeline_run_id       uuid NULL,
    agent_key             text NOT NULL REFERENCES public.external_agent_catalog(agent_key),
    external_execution_id text NOT NULL CHECK (char_length(trim(external_execution_id)) BETWEEN 2 AND 200),
    status                text NOT NULL DEFAULT 'queued' CHECK (
        status IN ('idle','queued','working','waiting_input','waiting_approval','blocked','done','gate_passed','gate_failed','failed','skipped','cancelled')
    ),
    stage_label           text NULL,
    progress              numeric(5,4) NULL CHECK (progress IS NULL OR (progress >= 0 AND progress <= 1)),
    attempt               integer NOT NULL DEFAULT 1 CHECK (attempt >= 1),
    model_name            text NULL,
    input_summary         jsonb NOT NULL DEFAULT '{}'::jsonb,
    output_summary        jsonb NOT NULL DEFAULT '{}'::jsonb,
    artifacts             jsonb NOT NULL DEFAULT '[]'::jsonb,
    metrics               jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_code            text NULL,
    error_message         text NULL,
    heartbeat_at          timestamptz NULL,
    started_at            timestamptz NULL,
    finished_at           timestamptz NULL,
    duration_ms           integer NULL CHECK (duration_ms IS NULL OR duration_ms >= 0),
    created_at            timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at            timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id),
    UNIQUE (channel_id, external_execution_id),
    CONSTRAINT fk_ext_exec_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_ext_exec_run_ws
        FOREIGN KEY (workspace_id, pipeline_run_id)
        REFERENCES public.external_pipeline_runs(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ext_exec_channel_agent_updated
    ON public.external_agent_executions (channel_id, agent_key, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ext_exec_pipeline_run
    ON public.external_agent_executions (pipeline_run_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ext_exec_channel_status
    ON public.external_agent_executions (workspace_id, channel_id, status);

CREATE TRIGGER trg_ext_exec_updated_at
    BEFORE UPDATE ON public.external_agent_executions
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 4. Feed append-only de eventos dos agentes externos (Realtime)
CREATE TABLE IF NOT EXISTS public.external_agent_events (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id    uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id      uuid NOT NULL,
    pipeline_run_id uuid NULL,
    execution_id    uuid NULL,
    agent_key       text NOT NULL REFERENCES public.external_agent_catalog(agent_key),
    event_type      text NOT NULL CHECK (
        event_type IN ('queued','started','progress','stage_changed','heartbeat','artifact_created','gate_passed','gate_failed','waiting_human','completed','failed','cancelled','log')
    ),
    level           text NOT NULL DEFAULT 'info' CHECK (level IN ('debug','info','warn','error')),
    message         text NOT NULL,
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_ext_events_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_ext_events_run_ws
        FOREIGN KEY (workspace_id, pipeline_run_id)
        REFERENCES public.external_pipeline_runs(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_ext_events_exec_ws
        FOREIGN KEY (workspace_id, execution_id)
        REFERENCES public.external_agent_executions(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ext_events_channel_cursor
    ON public.external_agent_events (channel_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_ext_events_workspace_channel
    ON public.external_agent_events (workspace_id, channel_id, id DESC);
CREATE INDEX IF NOT EXISTS idx_ext_events_run
    ON public.external_agent_events (pipeline_run_id, id DESC)
    WHERE pipeline_run_id IS NOT NULL;

CREATE TRIGGER trg_ext_events_immutable
    BEFORE UPDATE OR DELETE ON public.external_agent_events
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

-- 5. Tokens de ingestao para o projeto separado enviar telemetria sem expor service_role
CREATE TABLE IF NOT EXISTS public.external_ingest_tokens (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id   uuid NULL,
    label        text NOT NULL CHECK (char_length(trim(label)) BETWEEN 2 AND 120),
    token_prefix text NOT NULL,
    token_hash   text NOT NULL UNIQUE,
    created_by   uuid NOT NULL,
    revoked_at   timestamptz NULL,
    last_used_at timestamptz NULL,
    created_at   timestamptz NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_ext_tokens_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_ext_tokens_workspace
    ON public.external_ingest_tokens (workspace_id, created_at DESC);

-- 6. RLS & Grants
REVOKE ALL ON public.external_agent_catalog FROM PUBLIC, anon;
REVOKE ALL ON public.external_pipeline_runs FROM PUBLIC, anon;
REVOKE ALL ON public.external_agent_executions FROM PUBLIC, anon;
REVOKE ALL ON public.external_agent_events FROM PUBLIC, anon;
REVOKE ALL ON public.external_ingest_tokens FROM PUBLIC, anon;

GRANT SELECT ON public.external_agent_catalog TO authenticated;
GRANT SELECT ON public.external_pipeline_runs TO authenticated;
GRANT SELECT ON public.external_agent_executions TO authenticated;
GRANT SELECT ON public.external_agent_events TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.external_ingest_tokens TO authenticated;

ALTER TABLE public.external_agent_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.external_agent_catalog FORCE ROW LEVEL SECURITY;
ALTER TABLE public.external_pipeline_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.external_pipeline_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.external_agent_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.external_agent_executions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.external_agent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.external_agent_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.external_ingest_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.external_ingest_tokens FORCE ROW LEVEL SECURITY;

CREATE POLICY external_agent_catalog_read ON public.external_agent_catalog
    FOR SELECT TO authenticated USING (true);
CREATE POLICY external_pipeline_runs_read ON public.external_pipeline_runs
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY external_agent_executions_read ON public.external_agent_executions
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY external_agent_events_read ON public.external_agent_events
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));

CREATE POLICY external_ingest_tokens_select ON public.external_ingest_tokens
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY external_ingest_tokens_insert ON public.external_ingest_tokens
    FOR INSERT TO authenticated
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner','editor']) AND created_by = auth.uid());
CREATE POLICY external_ingest_tokens_update ON public.external_ingest_tokens
    FOR UPDATE TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner','editor']))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner','editor']));

-- 7. Views de leitura para o painel central (security_invoker = true)
CREATE OR REPLACE VIEW public.v_external_agent_latest_state
WITH (security_invoker = true) AS
SELECT
    c.workspace_id,
    c.id AS channel_id,
    cat.agent_key,
    cat.display_name,
    cat.group_key,
    cat.sub_group,
    cat.agent_kind,
    cat.source_path,
    cat.runtime_lang,
    cat.studio_room_key,
    cat.studio_agent_key,
    cat.pipeline_order,
    cat.description,
    cat.active,
    ex.id AS execution_id,
    ex.pipeline_run_id,
    pr.external_run_id,
    pr.title AS pipeline_title,
    pr.pipeline_kind,
    ex.external_execution_id,
    CASE
        WHEN ex.id IS NULL THEN 'idle'
        WHEN ex.status = 'working' AND (ex.heartbeat_at IS NULL OR ex.heartbeat_at < timezone('utc', now()) - interval '3 minutes') THEN 'no_signal'
        ELSE ex.status
    END AS status,
    ex.stage_label,
    ex.progress,
    ex.attempt,
    ex.model_name,
    ex.input_summary,
    ex.output_summary,
    ex.artifacts,
    ex.metrics,
    ex.error_code,
    ex.error_message,
    ex.heartbeat_at,
    ex.started_at,
    ex.finished_at,
    ex.duration_ms,
    ex.updated_at AS execution_updated_at
FROM public.channels AS c
CROSS JOIN public.external_agent_catalog AS cat
LEFT JOIN LATERAL (
    SELECT e.*
    FROM public.external_agent_executions AS e
    WHERE e.workspace_id = c.workspace_id
      AND e.channel_id = c.id
      AND e.agent_key = cat.agent_key
    ORDER BY e.updated_at DESC, e.created_at DESC
    LIMIT 1
) AS ex ON true
LEFT JOIN public.external_pipeline_runs AS pr
  ON pr.id = ex.pipeline_run_id
 AND pr.workspace_id = c.workspace_id
WHERE cat.active = true;

CREATE OR REPLACE VIEW public.v_external_room_rollup
WITH (security_invoker = true) AS
SELECT
    s.workspace_id,
    s.channel_id,
    s.studio_room_key AS room_key,
    COUNT(*) AS total_agents,
    COUNT(*) FILTER (WHERE s.status = 'working') AS working,
    COUNT(*) FILTER (WHERE s.status = 'queued') AS queued,
    COUNT(*) FILTER (WHERE s.status IN ('waiting_input','waiting_approval')) AS awaiting_human,
    COUNT(*) FILTER (WHERE s.status IN ('done','gate_passed')) AS done,
    COUNT(*) FILTER (WHERE s.status IN ('failed','gate_failed','blocked','no_signal')) AS failed
FROM public.v_external_agent_latest_state AS s
GROUP BY s.workspace_id, s.channel_id, s.studio_room_key;

CREATE OR REPLACE VIEW public.v_external_pipeline_summary
WITH (security_invoker = true) AS
SELECT
    pr.id,
    pr.workspace_id,
    pr.channel_id,
    pr.content_item_id,
    pr.external_run_id,
    pr.pipeline_kind,
    pr.title,
    pr.status,
    pr.current_agent_key,
    pr.progress,
    pr.total_agents,
    pr.completed_agents,
    pr.failed_agents,
    pr.host_name,
    pr.source_repo,
    pr.metadata,
    pr.started_at,
    pr.finished_at,
    pr.updated_at,
    COALESCE(
        (
            SELECT jsonb_agg(
                jsonb_build_object(
                    'agent_key', e.agent_key,
                    'status', CASE
                        WHEN e.status = 'working' AND (e.heartbeat_at IS NULL OR e.heartbeat_at < timezone('utc', now()) - interval '3 minutes') THEN 'no_signal'
                        ELSE e.status
                    END,
                    'stage_label', e.stage_label,
                    'progress', e.progress
                )
                ORDER BY e.updated_at DESC
            )
            FROM public.external_agent_executions AS e
            WHERE e.pipeline_run_id = pr.id
              AND e.status IN ('working','queued','waiting_input','waiting_approval','failed','gate_failed')
        ),
        '[]'::jsonb
    ) AS active_agents_json
FROM public.external_pipeline_runs AS pr;

GRANT SELECT ON public.v_external_agent_latest_state TO authenticated;
GRANT SELECT ON public.v_external_room_rollup TO authenticated;
GRANT SELECT ON public.v_external_pipeline_summary TO authenticated;

-- 8. Funcao atomica de ingestao (chamavel pelo backend ou service_role via Supabase RPC)
CREATE OR REPLACE FUNCTION public.ingest_external_agent_event(
    p_workspace_id          uuid,
    p_channel_id            uuid,
    p_agent_key             text,
    p_status                text,
    p_external_run_id       text DEFAULT NULL,
    p_pipeline_kind         text DEFAULT 'custom',
    p_run_title             text DEFAULT NULL,
    p_external_execution_id text DEFAULT NULL,
    p_stage_label           text DEFAULT NULL,
    p_progress              numeric DEFAULT NULL,
    p_model_name            text DEFAULT NULL,
    p_event_type            text DEFAULT NULL,
    p_level                 text DEFAULT 'info',
    p_message               text DEFAULT NULL,
    p_input_summary         jsonb DEFAULT '{}'::jsonb,
    p_output_summary        jsonb DEFAULT '{}'::jsonb,
    p_artifacts             jsonb DEFAULT '[]'::jsonb,
    p_metrics               jsonb DEFAULT '{}'::jsonb,
    p_error_code            text DEFAULT NULL,
    p_error_message         text DEFAULT NULL,
    p_host_name             text DEFAULT NULL,
    p_source_repo           text DEFAULT NULL,
    p_attempt               integer DEFAULT 1,
    p_metadata              jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_now            timestamptz := timezone('utc', now());
    v_run_key        text := COALESCE(NULLIF(trim(p_external_run_id), ''), 'default-' || to_char(v_now, 'YYYYMMDD'));
    v_exec_key       text := COALESCE(NULLIF(trim(p_external_execution_id), ''), v_run_key || ':' || p_agent_key || ':' || GREATEST(COALESCE(p_attempt, 1), 1)::text);
    v_pipeline_id    uuid;
    v_exec_id        uuid;
    v_event_id       bigint;
    v_is_terminal    boolean := p_status IN ('done','gate_passed','gate_failed','failed','skipped','cancelled');
    v_started_at     timestamptz;
    v_finished_at    timestamptz;
    v_duration_ms    integer;
    v_event_type     text;
    v_message        text;
    v_done_count     integer;
    v_fail_count     integer;
    v_working_count  integer;
    v_run_status     text;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM public.external_agent_catalog WHERE agent_key = p_agent_key) THEN
        RAISE EXCEPTION 'Agente externo desconhecido no catalogo: %', p_agent_key USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM public.channels WHERE workspace_id = p_workspace_id AND id = p_channel_id) THEN
        RAISE EXCEPTION 'Canal % nao pertence ao workspace %', p_channel_id, p_workspace_id USING ERRCODE = 'foreign_key_violation';
    END IF;

    -- 1. Upsert pipeline run
    INSERT INTO public.external_pipeline_runs (
        workspace_id, channel_id, external_run_id, pipeline_kind, title,
        status, current_agent_key, host_name, source_repo, metadata, started_at
    )
    VALUES (
        p_workspace_id, p_channel_id, v_run_key, COALESCE(NULLIF(trim(p_pipeline_kind), ''), 'custom'),
        COALESCE(NULLIF(trim(p_run_title), ''), v_run_key),
        CASE WHEN p_status IN ('waiting_input','waiting_approval') THEN 'waiting_human' ELSE 'running' END,
        p_agent_key, p_host_name, p_source_repo, COALESCE(p_metadata, '{}'::jsonb), v_now
    )
    ON CONFLICT (channel_id, external_run_id) DO UPDATE
    SET current_agent_key = CASE WHEN p_status = 'working' THEN EXCLUDED.current_agent_key ELSE public.external_pipeline_runs.current_agent_key END,
        title             = COALESCE(NULLIF(trim(p_run_title), ''), public.external_pipeline_runs.title),
        host_name         = COALESCE(NULLIF(trim(p_host_name), ''), public.external_pipeline_runs.host_name),
        source_repo       = COALESCE(NULLIF(trim(p_source_repo), ''), public.external_pipeline_runs.source_repo),
        metadata          = public.external_pipeline_runs.metadata || COALESCE(p_metadata, '{}'::jsonb),
        updated_at        = v_now
    RETURNING id INTO v_pipeline_id;

    -- 2. Determine timestamps for execution
    SELECT started_at INTO v_started_at
    FROM public.external_agent_executions
    WHERE channel_id = p_channel_id AND external_execution_id = v_exec_key;

    IF v_started_at IS NULL AND p_status IN ('working','done','gate_passed','gate_failed','failed','waiting_input','waiting_approval','blocked') THEN
        v_started_at := v_now;
    END IF;

    IF v_is_terminal THEN
        v_finished_at := v_now;
        IF v_started_at IS NOT NULL THEN
            v_duration_ms := GREATEST(0, floor(extract(epoch FROM (v_finished_at - v_started_at)) * 1000)::integer);
        END IF;
    ELSE
        v_finished_at := NULL;
        v_duration_ms := NULL;
    END IF;

    -- 3. Upsert agent execution
    INSERT INTO public.external_agent_executions (
        workspace_id, channel_id, pipeline_run_id, agent_key, external_execution_id,
        status, stage_label, progress, attempt, model_name,
        input_summary, output_summary, artifacts, metrics,
        error_code, error_message, heartbeat_at, started_at, finished_at, duration_ms
    )
    VALUES (
        p_workspace_id, p_channel_id, v_pipeline_id, p_agent_key, v_exec_key,
        p_status, p_stage_label,
        CASE WHEN p_progress IS NOT NULL THEN LEAST(1, GREATEST(0, p_progress)) WHEN p_status IN ('done','gate_passed') THEN 1 ELSE NULL END,
        GREATEST(COALESCE(p_attempt, 1), 1),
        p_model_name,
        COALESCE(p_input_summary, '{}'::jsonb),
        COALESCE(p_output_summary, '{}'::jsonb),
        COALESCE(p_artifacts, '[]'::jsonb),
        COALESCE(p_metrics, '{}'::jsonb),
        p_error_code, p_error_message, v_now, v_started_at, v_finished_at, v_duration_ms
    )
    ON CONFLICT (channel_id, external_execution_id) DO UPDATE
    SET pipeline_run_id = COALESCE(v_pipeline_id, public.external_agent_executions.pipeline_run_id),
        status          = EXCLUDED.status,
        stage_label     = COALESCE(EXCLUDED.stage_label, public.external_agent_executions.stage_label),
        progress        = COALESCE(EXCLUDED.progress, public.external_agent_executions.progress),
        attempt         = GREATEST(public.external_agent_executions.attempt, EXCLUDED.attempt),
        model_name      = COALESCE(EXCLUDED.model_name, public.external_agent_executions.model_name),
        input_summary   = CASE WHEN p_input_summary IS NOT NULL AND p_input_summary <> '{}'::jsonb THEN p_input_summary ELSE public.external_agent_executions.input_summary END,
        output_summary  = CASE WHEN p_output_summary IS NOT NULL AND p_output_summary <> '{}'::jsonb THEN p_output_summary ELSE public.external_agent_executions.output_summary END,
        artifacts       = CASE WHEN jsonb_array_length(COALESCE(p_artifacts, '[]'::jsonb)) > 0 THEN p_artifacts ELSE public.external_agent_executions.artifacts END,
        metrics         = public.external_agent_executions.metrics || COALESCE(p_metrics, '{}'::jsonb),
        error_code      = CASE WHEN EXCLUDED.status IN ('failed','gate_failed','blocked') THEN EXCLUDED.error_code ELSE NULL END,
        error_message   = CASE WHEN EXCLUDED.status IN ('failed','gate_failed','blocked') THEN EXCLUDED.error_message ELSE NULL END,
        heartbeat_at    = v_now,
        started_at      = COALESCE(public.external_agent_executions.started_at, v_started_at),
        finished_at     = v_finished_at,
        duration_ms     = COALESCE(v_duration_ms, public.external_agent_executions.duration_ms),
        updated_at      = v_now
    RETURNING id INTO v_exec_id;

    -- 4. Recompute counters on pipeline run
    SELECT
        COUNT(*) FILTER (WHERE status IN ('done','gate_passed','skipped')),
        COUNT(*) FILTER (WHERE status IN ('failed','gate_failed')),
        COUNT(*) FILTER (WHERE status IN ('working','queued','waiting_input','waiting_approval'))
    INTO v_done_count, v_fail_count, v_working_count
    FROM public.external_agent_executions
    WHERE pipeline_run_id = v_pipeline_id;

    v_run_status := CASE
        WHEN p_status IN ('waiting_input','waiting_approval') THEN 'waiting_human'
        WHEN v_working_count > 0 THEN 'running'
        WHEN v_fail_count > 0 THEN 'failed'
        WHEN v_done_count > 0 THEN 'completed'
        ELSE 'running'
    END;

    UPDATE public.external_pipeline_runs
    SET completed_agents = v_done_count,
        failed_agents    = v_fail_count,
        status           = v_run_status,
        finished_at      = CASE WHEN v_run_status IN ('completed','failed','cancelled') THEN v_now ELSE NULL END,
        progress         = CASE
            WHEN total_agents IS NOT NULL AND total_agents > 0 THEN LEAST(1.0, ROUND((v_done_count::numeric / total_agents::numeric), 4))
            ELSE progress
        END,
        updated_at       = v_now
    WHERE id = v_pipeline_id;

    -- 5. Append event
    v_event_type := COALESCE(
        NULLIF(trim(p_event_type), ''),
        CASE p_status
            WHEN 'queued' THEN 'queued'
            WHEN 'working' THEN 'started'
            WHEN 'done' THEN 'completed'
            WHEN 'gate_passed' THEN 'gate_passed'
            WHEN 'gate_failed' THEN 'gate_failed'
            WHEN 'waiting_input' THEN 'waiting_human'
            WHEN 'waiting_approval' THEN 'waiting_human'
            WHEN 'failed' THEN 'failed'
            WHEN 'cancelled' THEN 'cancelled'
            ELSE 'log'
        END
    );

    v_message := COALESCE(
        NULLIF(trim(p_message), ''),
        NULLIF(trim(p_stage_label), ''),
        p_agent_key || ' -> ' || p_status
    );

    INSERT INTO public.external_agent_events (
        workspace_id, channel_id, pipeline_run_id, execution_id,
        agent_key, event_type, level, message, payload
    )
    VALUES (
        p_workspace_id, p_channel_id, v_pipeline_id, v_exec_id,
        p_agent_key, v_event_type,
        COALESCE(NULLIF(trim(p_level), ''), CASE WHEN p_status IN ('failed','gate_failed') THEN 'error' WHEN p_status IN ('blocked','waiting_input','waiting_approval') THEN 'warn' ELSE 'info' END),
        v_message,
        jsonb_strip_nulls(jsonb_build_object(
            'status', p_status,
            'stage_label', p_stage_label,
            'progress', p_progress,
            'model_name', p_model_name,
            'duration_ms', v_duration_ms,
            'error_code', p_error_code,
            'metrics', NULLIF(p_metrics, '{}'::jsonb)
        ))
    )
    RETURNING id INTO v_event_id;

    RETURN jsonb_build_object(
        'pipeline_run_id', v_pipeline_id,
        'execution_id', v_exec_id,
        'event_id', v_event_id,
        'external_run_id', v_run_key,
        'external_execution_id', v_exec_key,
        'agent_key', p_agent_key,
        'status', p_status,
        'duration_ms', v_duration_ms
    );
END;
$$;

REVOKE ALL ON FUNCTION public.ingest_external_agent_event(
    uuid, uuid, text, text, text, text, text, text, text, numeric, text, text, text, text, jsonb, jsonb, jsonb, jsonb, text, text, text, text, integer, jsonb
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.ingest_external_agent_event(
    uuid, uuid, text, text, text, text, text, text, text, numeric, text, text, text, text, jsonb, jsonb, jsonb, jsonb, text, text, text, text, integer, jsonb
) TO service_role;

-- 9. Registrar tabelas externas no supabase_realtime para atualizacao instantanea na UI
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.external_agent_events;
        EXCEPTION WHEN duplicate_object THEN NULL; WHEN others THEN NULL;
        END;
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.external_agent_executions;
        EXCEPTION WHEN duplicate_object THEN NULL; WHEN others THEN NULL;
        END;
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.external_pipeline_runs;
        EXCEPTION WHEN duplicate_object THEN NULL; WHEN others THEN NULL;
        END;
    END IF;
END;
$$;
