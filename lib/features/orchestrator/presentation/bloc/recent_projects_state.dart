import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';

final class RecentProjectsState {
  const RecentProjectsState({
    this.projects = const <LocalProjectEntity>[],
    this.activeProjectId,
    this.expandedProjectIds = const <String>[],
    this.isLoading = false,
  });

  final List<LocalProjectEntity> projects;
  final String? activeProjectId;
  final List<String> expandedProjectIds;
  final bool isLoading;

  bool isProjectExpanded(String projectId) {
    return expandedProjectIds.contains(projectId);
  }

  RecentProjectsState copyWith({
    List<LocalProjectEntity>? projects,
    String? activeProjectId,
    bool clearActiveProjectId = false,
    List<String>? expandedProjectIds,
    bool? isLoading,
  }) {
    return RecentProjectsState(
      projects: projects ?? this.projects,
      activeProjectId: clearActiveProjectId
          ? null
          : activeProjectId ?? this.activeProjectId,
      expandedProjectIds: expandedProjectIds ?? this.expandedProjectIds,
      isLoading: isLoading ?? this.isLoading,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is RecentProjectsState &&
            other.isLoading == isLoading &&
            other.activeProjectId == activeProjectId &&
            _listEquals(other.projects, projects) &&
            _listEqualsStrings(other.expandedProjectIds, expandedProjectIds);
  }

  @override
  int get hashCode =>
      Object.hash(projects, activeProjectId, expandedProjectIds, isLoading);

  bool _listEquals(
    List<LocalProjectEntity> left,
    List<LocalProjectEntity> right,
  ) {
    if (left.length != right.length) {
      return false;
    }
    for (int index = 0; index < left.length; index++) {
      if (left[index] != right[index]) {
        return false;
      }
    }
    return true;
  }

  bool _listEqualsStrings(List<String> left, List<String> right) {
    if (left.length != right.length) {
      return false;
    }
    for (int index = 0; index < left.length; index++) {
      if (left[index] != right[index]) {
        return false;
      }
    }
    return true;
  }
}
