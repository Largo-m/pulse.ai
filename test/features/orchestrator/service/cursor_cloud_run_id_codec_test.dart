import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_run_id_codec.dart';

void main() {
  group('CursorCloudRunIdCodec', () {
    test('encode and decode round-trip agent and run ids', () {
      const String encoded = 'bc-agent-1::run-agent-1';

      final ({String agentId, String runId})? decoded =
          CursorCloudRunIdCodec.decode(encoded);

      expect(decoded, isNotNull);
      expect(decoded!.agentId, 'bc-agent-1');
      expect(decoded.runId, 'run-agent-1');
      expect(
        CursorCloudRunIdCodec.encode(
          agentId: decoded.agentId,
          runId: decoded.runId,
        ),
        encoded,
      );
    });
  });
}
