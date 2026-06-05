import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/import_flow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/import_project_flow_outcome_handler.dart';

void main() {
  group('ImportProjectFlowOutcomeHandler', () {
    test('success navigates then refreshes recent projects', () async {
      var navigated = false;
      var refreshed = false;
      var reset = false;

      await ImportProjectFlowOutcomeHandler.handle(
        state: ImportFlowState(
          status: ImportFlowStatus.success,
          project: LocalProjectEntity(
            id: 'uuid-repo',
            canonicalPath: '/tmp/repo',
            displayName: 'repo',
            lastAccessedAt: DateTime.utc(2026, 5, 15),
          ),
        ),
        onImportSuccessNavigate: () {
          navigated = true;
        },
        refreshRecentProjects: () async {
          refreshed = true;
        },
        showImportFailure: (_) {},
        resetImportFlow: () {
          reset = true;
        },
      );

      expect(navigated, isTrue);
      expect(refreshed, isTrue);
      expect(reset, isTrue);
    });

    test('failure shows feedback and resets import flow', () async {
      var failureShown = false;
      String? capturedMessage;
      var reset = false;

      await ImportProjectFlowOutcomeHandler.handle(
        state: const ImportFlowState(
          status: ImportFlowStatus.failure,
          failureMessage: 'permission denied',
        ),
        onImportSuccessNavigate: () {},
        refreshRecentProjects: () async {},
        showImportFailure: (String? failureMessage) {
          failureShown = true;
          capturedMessage = failureMessage;
        },
        resetImportFlow: () {
          reset = true;
        },
      );

      expect(failureShown, isTrue);
      expect(capturedMessage, 'permission denied');
      expect(reset, isTrue);
    });

    test('cancelled resets import flow without failure feedback', () async {
      var failureShown = false;
      var reset = false;

      await ImportProjectFlowOutcomeHandler.handle(
        state: const ImportFlowState(status: ImportFlowStatus.cancelled),
        onImportSuccessNavigate: () {},
        refreshRecentProjects: () async {},
        showImportFailure: (_) {
          failureShown = true;
        },
        resetImportFlow: () {
          reset = true;
        },
      );

      expect(failureShown, isFalse);
      expect(reset, isTrue);
    });

    test(
      'success without navigation still refreshes recent projects',
      () async {
        var refreshed = false;

        await ImportProjectFlowOutcomeHandler.handle(
          state: ImportFlowState(
            status: ImportFlowStatus.success,
            project: LocalProjectEntity(
              id: 'uuid-repo',
              canonicalPath: '/tmp/repo',
              displayName: 'repo',
              lastAccessedAt: DateTime.utc(2026, 5, 15),
            ),
          ),
          refreshRecentProjects: () async {
            refreshed = true;
          },
          showImportFailure: (_) {},
          resetImportFlow: () {},
        );

        expect(refreshed, isTrue);
      },
    );

    test('idle and loading do not trigger side effects', () async {
      var navigated = false;

      await ImportProjectFlowOutcomeHandler.handle(
        state: const ImportFlowState(status: ImportFlowStatus.loading),
        onImportSuccessNavigate: () {
          navigated = true;
        },
        refreshRecentProjects: () async {},
        showImportFailure: (_) {},
        resetImportFlow: () {},
      );

      expect(navigated, isFalse);
    });
  });
}
