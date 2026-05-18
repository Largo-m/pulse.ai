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

  static const String initializeAgentModalTitle = 'Novo agente';
  static const String initializeAgentCoreDirectiveLabel = 'Descrição:';
  static const String initializeAgentCoreDirectiveHint =
      'Defina o propósito central do agente.';
  static const String initializeAgentNameLabel = 'Nome: ';
  static const String initializeAgentNameHint = 'Ex.: Bot-SRE-01';
  static const String initializeAgentProjectLabel = 'Projeto:';
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
}
