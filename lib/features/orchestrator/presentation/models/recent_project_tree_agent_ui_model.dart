final class RecentProjectTreeAgentUiModel {
  const RecentProjectTreeAgentUiModel({
    required this.displayName,
    required this.isActive,
    this.isRunning = false,
  });

  final String displayName;
  final bool isActive;
  final bool isRunning;
}
