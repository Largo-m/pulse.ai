import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_git_branches_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/initialize_agent_branches_state.dart';

final class InitializeAgentBranchesCubit
    extends Cubit<InitializeAgentBranchesState> {
  InitializeAgentBranchesCubit({
    required ListLocalGitBranchesUseCase listLocalGitBranchesUseCase,
  }) : _listLocalGitBranchesUseCase = listLocalGitBranchesUseCase,
       super(const InitializeAgentBranchesState());

  final ListLocalGitBranchesUseCase _listLocalGitBranchesUseCase;

  Future<void> loadForProject({
    required String absolutePath,
    String? macosSecurityScopedBookmark,
  }) async {
    final int generation = state.loadGeneration + 1;
    emit(
      InitializeAgentBranchesState(
        status: BranchLoadStatus.loading,
        activePath: absolutePath,
        loadGeneration: generation,
      ),
    );

    final LocalGitBranchesResult result = await _listLocalGitBranchesUseCase(
      absolutePath: absolutePath,
      macosSecurityScopedBookmark: macosSecurityScopedBookmark,
    );

    if (generation != state.loadGeneration) {
      return;
    }

    switch (result.outcome) {
      case LocalGitBranchesOutcome.success:
        emit(
          InitializeAgentBranchesState(
            status: BranchLoadStatus.loaded,
            branches: result.branches,
            selectedBranch: _defaultSelectedBranch(result),
            activePath: absolutePath,
            loadGeneration: generation,
          ),
        );
      case LocalGitBranchesOutcome.notGitRepository:
        emit(
          InitializeAgentBranchesState(
            status: BranchLoadStatus.notGitRepository,
            activePath: absolutePath,
            loadGeneration: generation,
          ),
        );
      case LocalGitBranchesOutcome.permissionDenied:
        emit(
          InitializeAgentBranchesState(
            status: BranchLoadStatus.permissionDenied,
            activePath: absolutePath,
            loadGeneration: generation,
          ),
        );
      case LocalGitBranchesOutcome.failure:
        emit(
          InitializeAgentBranchesState(
            status: BranchLoadStatus.failure,
            activePath: absolutePath,
            loadGeneration: generation,
          ),
        );
    }
  }

  void selectBranch(String name) {
    if (state.status != BranchLoadStatus.loaded) {
      return;
    }

    emit(state.copyWith(selectedBranch: name));
  }

  void reset() {
    emit(const InitializeAgentBranchesState());
  }

  String? _defaultSelectedBranch(LocalGitBranchesResult result) {
    final String? headBranchName = result.headBranchName;
    if (headBranchName == null) {
      return null;
    }

    return result.branches.contains(headBranchName) ? headBranchName : null;
  }
}
