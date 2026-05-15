import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_state.dart';

abstract final class ImportProjectFlowOutcomeHandler {
  static Future<void> handle({
    required ImportFlowState state,
    required void Function() onImportSuccessNavigate,
    required Future<void> Function() refreshRecentProjects,
    required void Function() showImportFailure,
    required void Function() resetImportFlow,
  }) async {
    switch (state.status) {
      case ImportFlowStatus.success:
        onImportSuccessNavigate();
        await refreshRecentProjects();
        resetImportFlow();
      case ImportFlowStatus.failure:
        showImportFailure();
        resetImportFlow();
      case ImportFlowStatus.cancelled:
        resetImportFlow();
      case ImportFlowStatus.idle:
      case ImportFlowStatus.loading:
        break;
    }
  }
}
