import 'package:hive/hive.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_type_ids.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';

final class StreamEventEntityAdapter extends TypeAdapter<StreamEventEntity> {
  @override
  int get typeId => OrchestratorHiveTypeIds.streamEventEntity;

  @override
  StreamEventEntity read(BinaryReader reader) {
    final int fieldCount = reader.readByte();
    String runId = '';
    int sequence = 0;
    String eventType = '';
    String payloadSummary = '';
    DateTime timestamp = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);

    for (int i = 0; i < fieldCount; i++) {
      switch (reader.readByte()) {
        case 0:
          runId = reader.readString();
        case 1:
          sequence = reader.readInt();
        case 2:
          eventType = reader.readString();
        case 3:
          payloadSummary = reader.readString();
        case 4:
          timestamp = DateTime.fromMillisecondsSinceEpoch(
            reader.readInt(),
            isUtc: true,
          );
      }
    }

    return StreamEventEntity(
      runId: runId,
      sequence: sequence,
      eventType: eventType,
      payloadSummary: payloadSummary,
      timestamp: timestamp,
    );
  }

  @override
  void write(BinaryWriter writer, StreamEventEntity obj) {
    writer
      ..writeByte(5)
      ..writeByte(0)
      ..writeString(obj.runId)
      ..writeByte(1)
      ..writeInt(obj.sequence)
      ..writeByte(2)
      ..writeString(obj.eventType)
      ..writeByte(3)
      ..writeString(obj.payloadSummary)
      ..writeByte(4)
      ..writeInt(obj.timestamp.millisecondsSinceEpoch);
  }
}
