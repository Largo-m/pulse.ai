import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_state.dart';

abstract final class ImportProjectFlowOutcomeHandler {
  static Future<void> handle({
    required ImportFlowState state,
    void Function()? onImportSuccessNavigate,
    required Future<void> Function() refreshRecentProjects,
    required void Function(String? failureMessage) showImportFailure,
    required void Function() resetImportFlow,
  }) async {
    switch (state.status) {
      case ImportFlowStatus.success:
        onImportSuccessNavigate?.call();
        await refreshRecentProjects();
        resetImportFlow();
      case ImportFlowStatus.failure:
        showImportFailure(state.failureMessage);
        resetImportFlow();
      case ImportFlowStatus.cancelled:
        resetImportFlow();
      case ImportFlowStatus.idle:
      case ImportFlowStatus.loading:
        break;
    }
  }
}
