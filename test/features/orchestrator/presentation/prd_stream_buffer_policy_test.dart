import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_buffer_policy.dart';

void main() {
  test('maxInMemoryEvents is documented cap for live stream panel', () {
    expect(PrdStreamBufferPolicy.maxInMemoryEvents, greaterThan(0));
    expect(PrdStreamBufferPolicy.maxInMemoryEvents, 200);
  });
}
