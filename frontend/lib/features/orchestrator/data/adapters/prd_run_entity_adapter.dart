import 'package:hive/hive.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_type_ids.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';

final class PrdRunEntityAdapter extends TypeAdapter<PrdRunEntity> {
  @override
  int get typeId => OrchestratorHiveTypeIds.prdRunEntity;

  @override
  PrdRunEntity read(BinaryReader reader) {
    final int fieldCount = reader.readByte();
    String id = '';
    String workflowKey = '';
    String? cloudRunId;
    PrdRunStatus status = PrdRunStatus.queued;
    String? supersedesRunId;
    String? feedback;
    DateTime startedAt = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
    DateTime? endedAt;

    for (int i = 0; i < fieldCount; i++) {
      switch (reader.readByte()) {
        case 0:
          id = reader.readString();
        case 1:
          workflowKey = reader.readString();
        case 2:
          cloudRunId = reader.readBool() ? reader.readString() : null;
        case 3:
          status = PrdRunStatus.values[reader.readByte()];
        case 4:
          supersedesRunId = reader.readBool() ? reader.readString() : null;
        case 5:
          feedback = reader.readBool() ? reader.readString() : null;
        case 6:
          startedAt = DateTime.fromMillisecondsSinceEpoch(
            reader.readInt(),
            isUtc: true,
          );
        case 7:
          endedAt = reader.readBool()
              ? DateTime.fromMillisecondsSinceEpoch(
                  reader.readInt(),
                  isUtc: true,
                )
              : null;
      }
    }

    return PrdRunEntity(
      id: id,
      workflowKey: workflowKey,
      cloudRunId: cloudRunId,
      status: status,
      supersedesRunId: supersedesRunId,
      feedback: feedback,
      startedAt: startedAt,
      endedAt: endedAt,
    );
  }

  @override
  void write(BinaryWriter writer, PrdRunEntity obj) {
    writer
      ..writeByte(8)
      ..writeByte(0)
      ..writeString(obj.id)
      ..writeByte(1)
      ..writeString(obj.workflowKey)
      ..writeByte(2)
      ..writeBool(obj.cloudRunId != null);
    if (obj.cloudRunId != null) {
      writer.writeString(obj.cloudRunId!);
    }
    writer
      ..writeByte(3)
      ..writeByte(obj.status.index)
      ..writeByte(4)
      ..writeBool(obj.supersedesRunId != null);
    if (obj.supersedesRunId != null) {
      writer.writeString(obj.supersedesRunId!);
    }
    writer
      ..writeByte(5)
      ..writeBool(obj.feedback != null);
    if (obj.feedback != null) {
      writer.writeString(obj.feedback!);
    }
    writer
      ..writeByte(6)
      ..writeInt(obj.startedAt.millisecondsSinceEpoch)
      ..writeByte(7)
      ..writeBool(obj.endedAt != null);
    if (obj.endedAt != null) {
      writer.writeInt(obj.endedAt!.millisecondsSinceEpoch);
    }
  }
}
