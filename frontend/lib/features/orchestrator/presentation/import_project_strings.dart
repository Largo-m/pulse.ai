abstract final class ImportProjectStrings {
  static const String pageTitle = 'Importar projeto';
  static const String pageSubtitle =
      'Selecione uma origem para começar a orquestrar sua carga de trabalho agêntica.';

  static const String localBadge = 'Local';
  static const String localTitle = 'Workspace local';
  static const String localBody =
      'Monte um diretório do seu sistema de arquivos local diretamente no '
      'orquestrador. Ideal para prototipagem rápida e projetos com dependências '
      'de dados locais sensíveis.';
  static const String localFeatureZeroLatency = 'Sincronização sem latência';
  static const String localFeatureDirectIo = 'Acesso I/O direto';
  static const String selectLocal = 'Selecionar local';

  static const String remoteBadge = 'Remoto';
  static const String remoteTitle = 'Repositório remoto';
  static const String remoteBody =
      'Clone do GitHub, GitLab ou Bitbucket. Permite integração contínua e '
      'fluxos colaborativos de desenvolvimento agêntico com rastreamento '
      'automático de versão.';
  static const String remoteFeatureGitAuth = 'Autenticação com provedor Git';
  static const String remoteFeatureBranchManagement =
      'Gerenciamento de branches';
  static const String selectRemote = 'Selecionar remoto';

  static const String importLocalFailureMessage =
      'Não foi possível importar o projeto local. Verifique as permissões '
      'da pasta e tente novamente.';
  static const String importLocalPermissionFailureMessage =
      'Permissão negada para acessar a pasta selecionada.';
}
