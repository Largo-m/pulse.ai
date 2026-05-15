import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_result.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_state.dart';

final class ImportFlowCubit extends Cubit<ImportFlowState> {
  ImportFlowCubit({
    required ImportLocalProjectUseCase importLocalProjectUseCase,
  }) : _importLocalProjectUseCase = importLocalProjectUseCase,
       super(const ImportFlowState());

  final ImportLocalProjectUseCase _importLocalProjectUseCase;

  Future<void> importLocal() async {
    emit(const ImportFlowState(status: ImportFlowStatus.loading));

    final ImportLocalProjectResult result = await _importLocalProjectUseCase();

    switch (result.outcome) {
      case ImportLocalProjectOutcome.cancelled:
        emit(const ImportFlowState(status: ImportFlowStatus.cancelled));
      case ImportLocalProjectOutcome.success:
        emit(
          ImportFlowState(
            status: ImportFlowStatus.success,
            project: result.project,
          ),
        );
      case ImportLocalProjectOutcome.failure:
        emit(
          ImportFlowState(
            status: ImportFlowStatus.failure,
            failureMessage: result.failureMessage,
          ),
        );
    }
  }

  void reset() {
    emit(const ImportFlowState());
  }
}
