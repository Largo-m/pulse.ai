import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_run_status_mapper.dart';

void main() {
  group('CursorCloudRunStatusMapper', () {
    const CursorCloudRunStatusMapper mapper = CursorCloudRunStatusMapper();

    test('maps FINISHED to completed', () {
      expect(mapper.mapCloudStatus('FINISHED'), PrdRunStatus.completed);
    });

    test('maps ERROR and EXPIRED to failed', () {
      expect(mapper.mapCloudStatus('ERROR'), PrdRunStatus.failed);
      expect(mapper.mapCloudStatus('EXPIRED'), PrdRunStatus.failed);
    });

    test('maps CANCELLED to cancelled', () {
      expect(mapper.mapCloudStatus('cancelled'), PrdRunStatus.cancelled);
    });

    test('maps RUNNING and CREATING to running', () {
      expect(mapper.mapCloudStatus('RUNNING'), PrdRunStatus.running);
      expect(mapper.mapCloudStatus('CREATING'), PrdRunStatus.running);
    });

    test('returns null for unknown status', () {
      expect(mapper.mapCloudStatus('UNKNOWN'), isNull);
    });
  });
}
