enum BranchLoadStatus {
  initial,
  loading,
  loaded,
  notGitRepository,
  permissionDenied,
  failure,
}

final class InitializeAgentBranchesState {
  const InitializeAgentBranchesState({
    this.status = BranchLoadStatus.initial,
    this.branches = const <String>[],
    this.selectedBranch,
    this.activePath,
    this.loadGeneration = 0,
  });

  final BranchLoadStatus status;
  final List<String> branches;
  final String? selectedBranch;
  final String? activePath;
  final int loadGeneration;

  InitializeAgentBranchesState copyWith({
    BranchLoadStatus? status,
    List<String>? branches,
    String? selectedBranch,
    bool clearSelectedBranch = false,
    String? activePath,
    bool clearActivePath = false,
    int? loadGeneration,
  }) {
    return InitializeAgentBranchesState(
      status: status ?? this.status,
      branches: branches ?? this.branches,
      selectedBranch: clearSelectedBranch
          ? null
          : selectedBranch ?? this.selectedBranch,
      activePath: clearActivePath ? null : activePath ?? this.activePath,
      loadGeneration: loadGeneration ?? this.loadGeneration,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is InitializeAgentBranchesState &&
            other.status == status &&
            other.selectedBranch == selectedBranch &&
            other.activePath == activePath &&
            other.loadGeneration == loadGeneration &&
            _listEquals(other.branches, branches);
  }

  @override
  int get hashCode =>
      Object.hash(status, branches, selectedBranch, activePath, loadGeneration);

  bool _listEquals(List<String> left, List<String> right) {
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
