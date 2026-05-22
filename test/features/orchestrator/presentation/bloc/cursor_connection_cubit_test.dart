import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/remove_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/run_cursor_connection_preflight_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/save_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/validate_cursor_credential_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

import 'package:pulse_ai/features/orchestrator/service/fakes/fake_cursor_prd_agent_service.dart';

import '../../domain/service/fakes/fake_cursor_credential_store_service.dart';

void main() {
  group('CursorConnectionCubit', () {
    late FakeCursorPrdAgentService fakeService;
    late FakeCursorCredentialStoreService fakeStore;
    late RunCursorConnectionPreflightUseCase preflightUseCase;
    late ValidateCursorCredentialUseCase validateUseCase;
    late SaveCursorCredentialUseCase saveUseCase;
    late RemoveCursorCredentialUseCase removeUseCase;

    CursorConnectionCubit buildCubit() {
      return CursorConnectionCubit(
        runCursorConnectionPreflightUseCase: preflightUseCase,
        validateCursorCredentialUseCase: validateUseCase,
        saveCursorCredentialUseCase: saveUseCase,
        removeCursorCredentialUseCase: removeUseCase,
      );
    }

    setUp(() {
      fakeService = FakeCursorPrdAgentService();
      fakeStore = FakeCursorCredentialStoreService()
        ..throwOnWrite = null
        ..throwOnDelete = null;
      preflightUseCase = RunCursorConnectionPreflightUseCase(
        cursorPrdAgentService: fakeService,
      );
      validateUseCase = ValidateCursorCredentialUseCase(
        cursorPrdAgentService: fakeService,
      );
      saveUseCase = SaveCursorCredentialUseCase(credentialStore: fakeStore);
      removeUseCase = RemoveCursorCredentialUseCase(credentialStore: fakeStore);
    });

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'missing credential emits disconnected with remediation message key',
      build: buildCubit,
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightResult = left(
          const CursorConnectionFailure.missingCredential(),
        );
        await cubit.runPreflight();
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(status: CursorConnectionStatus.checking),
        const CursorConnectionState(
          status: CursorConnectionStatus.disconnected,
          remediationMessage:
              OrchestratorStrings.cursorConnectionMissingCredentialRemediation,
        ),
      ],
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'successful preflight emits connected',
      build: buildCubit,
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightResult = right(null);
        await cubit.runPreflight();
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(status: CursorConnectionStatus.checking),
        const CursorConnectionState(status: CursorConnectionStatus.connected),
      ],
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'network failure emits failure with disconnected remediation copy',
      build: buildCubit,
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightResult = left(
          const CursorConnectionFailure.network(),
        );
        await cubit.runPreflight();
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(status: CursorConnectionStatus.checking),
        const CursorConnectionState(
          status: CursorConnectionStatus.failure,
          remediationMessage:
              OrchestratorStrings.cursorConnectionDisconnectedRemediation,
        ),
      ],
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'unknown Cursor failure maps to disconnected remediation copy',
      build: buildCubit,
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightResult = left(
          const CursorConnectionFailure.unknown(),
        );
        await cubit.runPreflight();
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(status: CursorConnectionStatus.checking),
        const CursorConnectionState(
          status: CursorConnectionStatus.failure,
          remediationMessage:
              OrchestratorStrings.cursorConnectionDisconnectedRemediation,
        ),
      ],
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'non-cursor failure maps to disconnected remediation copy',
      build: buildCubit,
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightResult = left(
          const WorkflowPersistenceFailure.invalidSlug(),
        );
        await cubit.runPreflight();
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(status: CursorConnectionStatus.checking),
        const CursorConnectionState(
          status: CursorConnectionStatus.failure,
          remediationMessage:
              OrchestratorStrings.cursorConnectionDisconnectedRemediation,
        ),
      ],
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      '401 response emits failure state without exposing token in state toString',
      build: buildCubit,
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightResult = left(
          const CursorConnectionFailure.unauthorized(),
        );
        await cubit.runPreflight();
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(status: CursorConnectionStatus.checking),
        const CursorConnectionState(
          status: CursorConnectionStatus.failure,
          remediationMessage:
              OrchestratorStrings.cursorConnectionUnauthorizedRemediation,
        ),
      ],
      verify: (CursorConnectionCubit cubit) {
        final String stateString = cubit.state.toString();
        expect(stateString, isNot(contains('sk-live-')));
        expect(stateString, isNot(contains('Bearer ')));
        expect(
          cubit.state.remediationMessage,
          OrchestratorStrings.cursorConnectionUnauthorizedRemediation,
        );
      },
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'testDraftCredential success sets isDraftTestPassed and returns to idle',
      build: buildCubit,
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightCredentialResult = right(null);
        await cubit.testDraftCredential('draft-key');
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(
          settingsOperation: CursorSettingsOperationStatus.testing,
        ),
        const CursorConnectionState(
          isDraftTestPassed: true,
          settingsOperation: CursorSettingsOperationStatus.idle,
          settingsFeedbackMessageKey:
              OrchestratorStrings.cursorSettingsTestSuccessFeedback,
        ),
      ],
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'testDraftCredential 401 clears flag and sets unauthorized feedback key',
      build: buildCubit,
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightCredentialResult = left(
          const CursorConnectionFailure.unauthorized(),
        );
        await cubit.testDraftCredential('bad-key');
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(
          settingsOperation: CursorSettingsOperationStatus.testing,
        ),
        const CursorConnectionState(
          settingsFeedbackMessageKey:
              OrchestratorStrings.cursorSettingsUnauthorizedFeedback,
          settingsOperation: CursorSettingsOperationStatus.idle,
        ),
      ],
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'saveDraftCredential without test does not write to store',
      build: buildCubit,
      act: (CursorConnectionCubit cubit) async {
        await cubit.saveDraftCredential('new-key');
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(
          settingsFeedbackMessageKey:
              OrchestratorStrings.cursorSettingsSaveBlockedWithoutTest,
        ),
      ],
      verify: (_) {
        expect(fakeStore.storedCredential, isNull);
      },
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'saveDraftCredential after successful test persists and emits connected',
      build: buildCubit,
      seed: () => const CursorConnectionState(isDraftTestPassed: true),
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightResult = right(null);
        await cubit.saveDraftCredential('saved-key');
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(
          isDraftTestPassed: true,
          settingsOperation: CursorSettingsOperationStatus.saving,
        ),
        const CursorConnectionState(
          isDraftTestPassed: true,
          status: CursorConnectionStatus.checking,
          settingsOperation: CursorSettingsOperationStatus.idle,
        ),
        const CursorConnectionState(status: CursorConnectionStatus.connected),
      ],
      verify: (_) {
        expect(fakeStore.storedCredential, 'saved-key');
      },
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'saveDraftCredential store failure surfaces save failed feedback',
      build: buildCubit,
      seed: () => const CursorConnectionState(isDraftTestPassed: true),
      setUp: () {
        fakeStore.throwOnWrite = Exception('keychain entitlement missing');
      },
      act: (CursorConnectionCubit cubit) async {
        await cubit.saveDraftCredential('saved-key');
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(
          isDraftTestPassed: true,
          settingsOperation: CursorSettingsOperationStatus.saving,
        ),
        const CursorConnectionState(
          isDraftTestPassed: false,
          settingsOperation: CursorSettingsOperationStatus.idle,
          settingsFeedbackMessageKey:
              OrchestratorStrings.cursorSettingsSaveFailedFeedback,
        ),
      ],
      verify: (_) {
        expect(fakeStore.storedCredential, isNull);
      },
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'removeCredential deletes store and preflight yields disconnected',
      build: buildCubit,
      seed: () =>
          const CursorConnectionState(status: CursorConnectionStatus.connected),
      setUp: () {
        fakeStore.storedCredential = 'stored-key';
      },
      act: (CursorConnectionCubit cubit) async {
        fakeService.nextPreflightResult = left(
          const CursorConnectionFailure.missingCredential(),
        );
        await cubit.removeCredential();
      },
      expect: () => <CursorConnectionState>[
        const CursorConnectionState(
          status: CursorConnectionStatus.connected,
          settingsOperation: CursorSettingsOperationStatus.removing,
        ),
        const CursorConnectionState(
          status: CursorConnectionStatus.checking,
          settingsOperation: CursorSettingsOperationStatus.idle,
        ),
        const CursorConnectionState(
          status: CursorConnectionStatus.disconnected,
          remediationMessage:
              OrchestratorStrings.cursorConnectionMissingCredentialRemediation,
        ),
      ],
      verify: (_) {
        expect(fakeStore.storedCredential, isNull);
      },
    );

    blocTest<CursorConnectionCubit, CursorConnectionState>(
      'resetSettingsSession clears draft test flag and feedback',
      build: buildCubit,
      seed: () => const CursorConnectionState(
        isDraftTestPassed: true,
        settingsOperation: CursorSettingsOperationStatus.testing,
        settingsFeedbackMessageKey:
            OrchestratorStrings.cursorSettingsUnauthorizedFeedback,
      ),
      act: (CursorConnectionCubit cubit) {
        cubit.resetSettingsSession();
      },
      expect: () => <CursorConnectionState>[const CursorConnectionState()],
    );

    test('onDraftCredentialChanged clears isDraftTestPassed', () async {
      final CursorConnectionCubit cubit = buildCubit();
      cubit.emit(
        const CursorConnectionState(
          isDraftTestPassed: true,
          settingsFeedbackMessageKey:
              OrchestratorStrings.cursorSettingsUnauthorizedFeedback,
        ),
      );

      cubit.onDraftCredentialChanged();

      expect(cubit.state.isDraftTestPassed, isFalse);
      expect(cubit.state.settingsFeedbackMessageKey, isNull);
      await cubit.close();
    });
  });
}
