import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

import '../../domain/service/fakes/fake_cursor_prd_agent_service.dart';

void main() {
  group('CursorConnectionCubit', () {
    late FakeCursorPrdAgentService fakeService;

    CursorConnectionCubit buildCubit() {
      return CursorConnectionCubit(cursorPrdAgentService: fakeService);
    }

    setUp(() {
      fakeService = FakeCursorPrdAgentService();
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
  });
}
