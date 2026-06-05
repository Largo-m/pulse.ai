final class RecentProjectTreeAgentUiModel {
  const RecentProjectTreeAgentUiModel({
    required this.slug,
    required this.displayName,
    required this.isActive,
    this.isRunning = false,
  });

  final String slug;
  final String displayName;
  final bool isActive;
  final bool isRunning;
}
