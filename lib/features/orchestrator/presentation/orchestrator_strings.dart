abstract final class OrchestratorStrings {
  static const String brandName = 'Pulse.AI';

  static const String workspacesNav = 'Espaços de trabalho';
  static const String importProject = 'Importar projeto';

  static const String breadcrumbSystem = 'SISTEMA';
  static const String breadcrumbInitialization = 'INICIALIZAÇÃO';
  static const String statusStandby = 'EM ESPERA';

  static const String emptyStateTitle = 'Bem-vindo ao Pulse.AI';
  static const String emptyStateSubtitle =
      'O ambiente de orquestração agentica está inicializado e em espera. '
      'Configure seu workspace para começar a gerenciar fluxos de trabalho multiagente.';

  static const String localProjectTitle = 'Abrir projeto local';
  static const String localProjectBody =
      'Monte um diretório local com os arquivos de configuração do agente '
      'e os grafos de tarefas.';
  static const String localProjectButton = 'Inicializar local';

  static const String remoteProjectTitle = 'Clonar repositório Git';
  static const String remoteProjectBody =
      'Sincronize um projeto de orquestração existente do GitHub, GitLab '
      'ou um remoto personalizado.';
  static const String remoteProjectButton = 'Conectar remoto';

  static const String comingSoonMessage =
      'Em breve: integração ainda não disponível.';

  static const String recentProjectsSectionTitle = 'Projetos recentes';
  static const String recentProjectNewButtonTooltip = 'Novo projeto';
  static const String recentProjectSelectSemantics = 'Selecionar projeto';
  static const String recentProjectActiveSemantics = 'Projeto ativo';
  static const String recentProjectExpandSemantics = 'Expandir projeto';
  static const String recentProjectCollapseSemantics = 'Recolher projeto';
  static const String recentProjectAgentSelectSemantics =
      'Abrir workspace do workflow';

  static const String initializeAgentModalTitle = 'Novo agente';
  static const String initializeAgentCoreDirectiveLabel = 'Descrição:';
  static const String initializeAgentCoreDirectiveHint =
      'Defina o propósito central do agente.';
  static const String initializeAgentNameLabel = 'Nome: ';
  static const String initializeAgentNameHint = 'Ex.: Bot-SRE-01';
  static const String initializeAgentProjectLabel = 'Projeto:';
  static const String initializeAgentSlugLabel = 'Slug do workflow:';
  static const String initializeAgentSlugHint = 'Ex.: cursor-workflow-agents';
  static const String initializeAgentSlugRequiredError =
      'Informe um slug para o workflow.';
  static const String initializeAgentSlugInvalidFormatError =
      'O slug deve estar em kebab-case (letras minúsculas, números e hífens).';
  static const String initializeAgentSlugCollisionError =
      'Já existe um workflow com este slug neste projeto.';
  static const String initializeAgentCreateWorkflowFailure =
      'Não foi possível criar o workflow. Tente novamente.';
  static const String initializeAgentBranchLabel = 'Branch:';
  static const String initializeAgentBranchesLoading = 'Carregando branches…';
  static const String initializeAgentBranchesNotGit =
      'Este projeto não é um repositório Git.';
  static const String initializeAgentBranchesLoadFailed =
      'Não foi possível carregar as branches deste projeto.';
  static const String initializeAgentBranchesPermissionDenied =
      'Sem permissão para acessar este projeto. Reimporte a pasta do projeto.';
  static const String initializeAgentBranchesLoadingSemantics =
      'Carregando branches do projeto';
  static const String initializeAgentBranchesNotGitSemantics =
      'Projeto sem repositório Git; seleção de branch indisponível';
  static const String initializeAgentBranchesLoadFailedSemantics =
      'Falha ao carregar branches do projeto';
  static const String initializeAgentBranchesPermissionDeniedSemantics =
      'Sem permissão para acessar o projeto; reimporte a pasta';
  static const String initializeAgentProjectEmptyOption =
      'Nenhum projeto disponível';
  static const String initializeAgentCloseSemantics = 'Fechar';
  static const String initializeAgentCancelButton = 'Cancelar';
  static const String initializeAgentSubmitButton = 'Salvar';

  static const String workflowPhasePrd = 'PRD';
  static const String workflowPhaseTechspec = 'Techspec';
  static const String workflowPhaseTasks = 'Tasks';
  static const String workflowPhaseQa = 'QA';
  static const String workflowPhaseReview = 'Review';

  static const String workflowTechspecPrdRequiredTitle =
      'Aprove o PRD para continuar';
  static const String workflowTechspecPrdRequiredSubtitle =
      'A fase de TechSpec ficará disponível após você aprovar o PRD deste '
      'workflow no workspace PRD.';
  static const String workflowTechspecPrdRequiredSemantics =
      'TechSpec bloqueada até aprovação do PRD';

  static const String workflowTechspecEmptyTitle =
      'Nenhuma especificação técnica ainda';
  static const String workflowTechspecEmptySubtitle =
      'Pronto para definir a arquitetura? Você pode deixar a IA gerar a '
      'techspec inicial com base no PRD ou importar seu próprio documento.';
  static const String workflowTechspecInitializeButton = 'Inicializar techspec';
  static const String workflowTechspecPrdCompleteBanner =
      'Fase de PRD concluída. 12 requisitos prontos para processamento.';
  static const String workflowTechspecInstructionPlaceholder =
      'Adicionar instrução manual à especificação técnica…';
  static const String workflowTechspecApplyButton = 'Aplicar';
  static const String workflowTechspecInitializeSemantics =
      'Inicializar especificação técnica com IA';
  static const String workflowTechspecApplySemantics =
      'Aplicar instrução manual à especificação técnica';
  static const String workflowTechspecMappingTitle = 'MAPEAMENTO ARQUITETURAL';
  static const String workflowTechspecMappingSubtitle =
      'A IA está convertendo requisitos de produto em decisões de arquitetura, '
      'contratos e dependências entre módulos.';
  static const String workflowArchiveTitle = 'ARQUIVO';
  static const String workflowArchiveApprovedStatus = 'APROVADO';
  static const String workflowArchivePrdFileNamePrefix = 'PRD_Rascunho_';

  static String prdArtifactFileName(String workflowSlug) {
    return '$prdArtifactFileNamePrefix$workflowSlug.md';
  }

  static String workflowArchivePrdFileName(String workflowSlug) {
    return '$workflowArchivePrdFileNamePrefix$workflowSlug.md';
  }

  static const String cursorConnectionMissingCredentialRemediation =
      'Configure a chave da API do Cursor nas configurações para iniciar '
      'execuções do agente PRD.';
  static const String cursorConnectionUnauthorizedRemediation =
      'A credencial do Cursor foi recusada (401). Atualize a chave da API '
      'nas configurações e tente novamente.';
  static const String cursorConnectionDisconnectedRemediation =
      'Não foi possível verificar a conexão com o Cursor. Confira a rede e '
      'a chave da API nas configurações.';
  static const String cursorConnectionCheckingSemantics =
      'Verificando conexão com o Cursor';
  static const String cursorConnectionConnectedSemantics =
      'Conexão com o Cursor verificada';
  static const String cursorConnectionDisconnectedSemantics =
      'Cursor desconectado; configure a credencial';
  static const String cursorConnectionBannerCta = 'Abrir configurações';
  static const String cursorConnectionBannerSemantics =
      'Banner de conexão com o Cursor; credencial ausente ou inválida';

  static const String cursorSettingsModalTitle = 'Integração Cursor';
  static const String cursorSettingsApiKeyLabel = 'Chave da API do Cursor';
  static const String cursorSettingsApiKeyHint =
      'Cole a chave de Cloud Agents do painel do Cursor';
  static const String cursorSettingsHelperText =
      'A chave não é exibida após salvar. Use Testar antes de Salvar.';
  static const String cursorSettingsConfiguredStatus =
      'Chave configurada neste dispositivo';
  static const String cursorSettingsTestButton = 'Testar conexão';
  static const String cursorSettingsSaveButton = 'Salvar';
  static const String cursorSettingsRemoveButton = 'Remover';
  static const String cursorSettingsCancelButton = 'Cancelar';
  static const String cursorSettingsCloseSemantics =
      'Fechar configurações do Cursor';
  static const String cursorSettingsModalSemantics =
      'Configurações da integração Cursor';
  static const String cursorSettingsApiKeyFieldSemantics =
      'Campo para colar a chave da API do Cursor';
  static const String cursorSettingsTestButtonSemantics =
      'Testar a chave da API do Cursor sem salvar';
  static const String cursorSettingsSaveButtonSemantics =
      'Salvar a chave da API do Cursor após teste bem-sucedido';
  static const String cursorSettingsRemoveButtonSemantics =
      'Remover a chave da API do Cursor armazenada';
  static const String cursorSettingsDocumentationUrl =
      'https://cursor.com/docs/cloud-agent/api/endpoints';
  static const String cursorSettingsDocumentationLinkLabel =
      'Documentação oficial do Cursor (Cloud Agents)';
  static const String cursorSettingsDocumentationLinkSemantics =
      'Abrir documentação oficial do Cursor em um navegador externo';
  static const String cursorSettingsRemoveConfirmTitle =
      'Remover chave do Cursor?';
  static const String cursorSettingsRemoveConfirmBody =
      'A chave armazenada será apagada deste dispositivo. Execuções do agente PRD '
      'ficarão bloqueadas até você configurar uma nova chave.';
  static const String cursorSettingsRemoveConfirmButton = 'Remover';
  static const String cursorSettingsRemoveCancelButton = 'Cancelar';
  static const String cursorSettingsRemoveConfirmSemantics =
      'Confirmar remoção da chave da API do Cursor';
  static const String cursorSettingsRemoveCancelSemantics =
      'Cancelar remoção da chave da API do Cursor';

  static const String cursorSettingsSaveBlockedWithoutTest =
      'Teste a conexão antes de salvar a chave.';
  static const String cursorSettingsUnauthorizedFeedback =
      'Chave recusada (401). Verifique a chave da API do Cursor.';
  static const String cursorSettingsMissingCredentialFeedback =
      'Informe uma chave da API do Cursor válida.';
  static const String cursorSettingsNetworkFeedback =
      'Não foi possível validar a chave. Confira a rede, permissões do app no macOS '
      'e tente novamente.';
  static const String cursorSettingsTestSuccessFeedback =
      'Conexão verificada. Você já pode salvar a chave.';
  static const String cursorSettingsSaveFailedFeedback =
      'Não foi possível salvar a chave neste dispositivo. Reinicie o app e tente '
      'novamente.';
  static const String cursorSettingsUnknownFeedback =
      'Não foi possível validar a chave. Tente novamente.';

  static const String prdWorkflowStatusNotStarted = 'Não iniciado';
  static const String prdWorkflowStatusRunning = 'Em execução';
  static const String prdWorkflowStatusPendingApproval = 'Aguardando aprovação';
  static const String prdWorkflowStatusApproved = 'Aprovado';
  static const String prdWorkflowStatusFailed = 'Falhou';
  static const String prdWorkflowStatusCancelled = 'Cancelado';

  static const String prdWorkflowStreamEmpty =
      'Nenhum evento de execução ainda. Inicie o agente PRD para ver o stream ao vivo.';
  static const String prdWorkflowStartButton = 'Iniciar agente PRD';
  static const String prdWorkflowStartSemantics =
      'Iniciar execução do agente PRD com a diretiva do workflow';
  static const String prdWorkflowStartRetryButton = 'Tentar novamente';
  static const String prdWorkflowStartRetrySemantics =
      'Reiniciar execução do agente PRD após falha ou cancelamento';
  static const String prdWorkflowCancelButton = 'Cancelar execução';
  static const String prdWorkflowCancelSemantics =
      'Cancelar execução do agente PRD em andamento';
  static const String prdWorkflowStreamPanelSemantics =
      'Painel de stream ao vivo da execução PRD';
  static const String prdWorkflowSystemProcessingTitle =
      'PROCESSAMENTO DO SISTEMA';
  static const String prdArtifactDraftedMessage =
      'A IA elaborou um rascunho de PRD com base nos seus requisitos.';
  static const String prdArtifactRequestRevisionsButton = 'Solicitar revisões';
  static const String prdArtifactApproveButton = 'Aprovar artefato';
  static const String prdArtifactExpandSemantics =
      'Expandir visualização do rascunho do PRD';
  static const String prdArtifactFileNamePrefix = 'PRD_Rascunho_';
  static const String prdWorkflowRunStatusRunningSemantics =
      'Execução PRD em andamento';
  static const String prdWorkflowRunStatusPendingApprovalSemantics =
      'Execução PRD concluída; aguardando aprovação';
  static const String prdWorkflowRunStatusFailedSemantics =
      'Execução PRD falhou';
  static const String prdWorkflowRunStatusCancelledSemantics =
      'Execução PRD cancelada';

  static const String prdWorkflowUserActionRequiredTitle =
      'Ação necessária no Cursor';
  static const String prdWorkflowUserActionRequiredBody =
      'O agente sinalizou que precisa de uma ação sua no Cursor. '
      'Conclua a etapa pendente para retomar o stream.';

  static const String prdWorkflowRunFailedGeneric =
      'A execução do agente PRD falhou. Tente novamente ou verifique a conexão.';
  static const String prdWorkflowStreamUnavailable =
      'O stream da execução ficou indisponível. Verifique a rede e tente de novo.';
  static const String prdWorkflowSessionRestoreFailed =
      'Não foi possível restaurar a última sessão PRD. Verifique a conexão e tente '
      'novamente.';

  static const String prdWorkflowSessionEmptyTitle = 'Nenhuma sessão anterior';
  static const String prdWorkflowSessionEmptyBody =
      'Ainda não há uma execução finalizada neste workflow. Inicie o agente PRD '
      'para gerar o primeiro histórico.';
  static const String prdWorkflowSessionEmptySemantics =
      'Workspace PRD sem sessão finalizada anterior';

  static const String prdWorkflowSessionInProgressTitle =
      'Execução em andamento';
  static const String prdWorkflowSessionInProgressBody =
      'O agente PRD está processando esta execução. O log completo ficará '
      'disponível quando a run for finalizada.';
  static const String prdWorkflowSessionInProgressSemantics =
      'Execução PRD em andamento; log completo indisponível até a finalização';

  static const String prdWorkflowSessionRestoreFailedTitle =
      'Não foi possível carregar o histórico';
  static const String prdWorkflowSessionRestoreRetryButton =
      'Tentar carregar novamente';
  static const String prdWorkflowSessionRestoreRetrySemantics =
      'Tentar restaurar novamente a última sessão PRD';
  static const String prdWorkflowSessionRestoreFailedSemantics =
      'Falha ao restaurar histórico da sessão PRD';
  static const String prdWorkflowSessionRestoreTerminalHint =
      'O log ficará disponível após carregar o histórico com sucesso.';

  static const String prdWorkflowNewRunOverlayTitle =
      'Nova execução em andamento';
  static const String prdWorkflowNewRunOverlayBody =
      'Uma nova run do agente PRD está ativa. O histórico abaixo é da sessão '
      'anterior; o log ao vivo aparecerá quando esta execução for finalizada.';
  static const String prdWorkflowNewRunOverlaySemantics =
      'Banner: nova execução PRD em andamento sobre sessão restaurada';

  static const String prdWorkflowConversationSectionTitle =
      'Conversa com o agente';
  static const String prdWorkflowConversationSectionSemantics =
      'Lista de mensagens da conversa restaurada do agente PRD';
  static const String prdWorkflowConversationUserRoleLabel = 'Você';
  static const String prdWorkflowConversationAgentRoleLabel = 'Agente';

  static const String prdWorkflowStreamEventStatus = 'Atualização de status';
  static const String prdWorkflowStreamEventAssistant =
      'Resposta do assistente';
  static const String prdWorkflowStreamEventThinking = 'Raciocínio do agente';
  static const String prdWorkflowStreamEventToolCall = 'Chamada de ferramenta';
  static const String prdWorkflowStreamEventDone = 'Execução concluída';
  static const String prdWorkflowStreamEventHeartbeat = 'Heartbeat';
  static const String prdWorkflowStreamEventGeneric = 'Evento de execução';

  static const String prdReviewRepoContextLabel = 'Repositório';
  static const String prdReviewBranchContextLabel = 'Branch';
  static const String prdReviewUserEditedBadge = 'Editado pelo usuário';
  static const String prdReviewUserEditedBadgeSemantics =
      'PRD editado manualmente pelo usuário';
  static const String prdReviewSaveDraftButton = 'Salvar rascunho';
  static const String prdReviewSaveDraftSemantics =
      'Salvar rascunho do PRD em edição';
  static const String prdReviewApproveButton = 'Aprovar PRD';
  static const String prdReviewApproveSemantics =
      'Aprovar PRD com o conteúdo atual do editor';
  static const String prdReviewRejectButton = 'Rejeitar';
  static const String prdReviewRejectSemantics =
      'Rejeitar PRD e enviar feedback para nova execução do agente';
  static const String prdReviewFeedbackPlaceholder =
      'Descreva o que deve mudar no PRD (ex.: adicionar requisitos de segurança)…';
  static const String prdReviewFeedbackSubmitButton = 'Enviar feedback';
  static const String prdReviewFeedbackSubmitSemantics =
      'Rejeitar PRD e iniciar nova execução com o feedback informado';
  static const String prdReviewUnsavedOverwriteTitle = 'Substituir edições?';
  static const String prdReviewUnsavedOverwriteBody =
      'Uma nova execução do agente gerou outro rascunho. Salve suas alterações '
      'ou confirme para descartá-las e carregar o novo conteúdo.';
  static const String prdReviewUnsavedOverwriteConfirm = 'Substituir';
  static const String prdReviewUnsavedOverwriteCancel = 'Manter edição';
  static const String prdReviewUnsavedOverwriteConfirmSemantics =
      'Descartar edições não salvas e carregar o novo rascunho do agente';
  static const String prdReviewUnsavedOverwriteCancelSemantics =
      'Manter o texto atual do editor';
  static const String prdArtifactMissing =
      'O arquivo do artefato não foi encontrado no disco. Gere ou restaure o '
      'PRD para continuar.';
  static String prdArtifactRestoredRunLabel(String runId) {
    return 'Execução: $runId';
  }

  static const String prdAdrListSectionTitle = 'Decisões de arquitetura (ADR)';
  static const String prdAdrListSectionSemantics = 'Lista de ADRs do workflow';
  static const String prdAdrListLoadFailed =
      'Não foi possível carregar os ADRs deste workflow.';

  static const String prdReviewLoadFailed =
      'Não foi possível carregar o rascunho do PRD.';
  static const String prdReviewActionFailed =
      'Não foi possível concluir a ação de revisão. Tente novamente.';
  static const String prdReviewEditorSemantics = 'Editor markdown do PRD';
  static const String prdReviewRepoContextSemantics =
      'Caminho do repositório local em modo somente leitura';
  static const String prdReviewBranchContextSemantics =
      'Branch do fluxo em modo somente leitura';
}
