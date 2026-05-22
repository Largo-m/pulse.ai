import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_workflow_adrs_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_adr_list_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_adr_list_load_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_artifact_presentation.dart';

final class PrdAdrListCubit extends Cubit<PrdAdrListState> {
  PrdAdrListCubit({required ListWorkflowAdrsUseCase listWorkflowAdrsUseCase})
    : _listWorkflowAdrsUseCase = listWorkflowAdrsUseCase,
      super(const PrdAdrListState());

  final ListWorkflowAdrsUseCase _listWorkflowAdrsUseCase;

  String? _projectId;
  String? _slug;

  void bindContext({required String projectId, required String slug}) {
    _projectId = projectId;
    _slug = slug;
  }

  Future<void> loadAdrs() async {
    final String? projectId = _projectId;
    final String? slug = _slug;
    if (projectId == null || slug == null) {
      return;
    }

    emit(
      state.copyWith(
        loadStatus: PrdAdrListLoadStatus.loading,
        clearFailureMessageKey: true,
      ),
    );

    final Either<Failure, List<AdrEntry>> result =
        await _listWorkflowAdrsUseCase(projectId: projectId, slug: slug);

    if (isClosed) {
      return;
    }

    if (result.isLeft()) {
      final Failure failure = result.getLeft().toNullable()!;
      emit(
        state.copyWith(
          loadStatus: PrdAdrListLoadStatus.error,
          entries: const <AdrEntry>[],
          failureMessageKey: _failureMessageKey(failure),
        ),
      );
      return;
    }

    final List<AdrEntry> entries = result.getRight().toNullable()!;
    emit(
      state.copyWith(
        loadStatus: PrdAdrListLoadStatus.ready,
        entries: entries,
        clearFailureMessageKey: true,
      ),
    );
  }

  String _failureMessageKey(Failure failure) {
    if (failure is ArtifactPersistenceFailure &&
        failure.code == ArtifactPersistenceFailureCode.notFound) {
      return PrdArtifactFailureMessageKeys.missingArtifact;
    }
    return PrdArtifactFailureMessageKeys.adrListLoadFailed;
  }
}
