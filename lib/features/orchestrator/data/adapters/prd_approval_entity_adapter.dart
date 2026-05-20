import 'package:hive/hive.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_type_ids.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';

final class PrdApprovalEntityAdapter extends TypeAdapter<PrdApprovalEntity> {
  @override
  int get typeId => OrchestratorHiveTypeIds.prdApprovalEntity;

  @override
  PrdApprovalEntity read(BinaryReader reader) {
    final int fieldCount = reader.readByte();
    String workflowKey = '';
    PrdApprovalStatus status = PrdApprovalStatus.draft;
    DateTime? approvedAt;
    DateTime? lastEditedAt;
    String? sourceRunId;

    for (int i = 0; i < fieldCount; i++) {
      switch (reader.readByte()) {
        case 0:
          workflowKey = reader.readString();
        case 1:
          status = PrdApprovalStatus.values[reader.readByte()];
        case 2:
          approvedAt = reader.readBool()
              ? DateTime.fromMillisecondsSinceEpoch(
                  reader.readInt(),
                  isUtc: true,
                )
              : null;
        case 3:
          lastEditedAt = reader.readBool()
              ? DateTime.fromMillisecondsSinceEpoch(
                  reader.readInt(),
                  isUtc: true,
                )
              : null;
        case 4:
          sourceRunId = reader.readBool() ? reader.readString() : null;
      }
    }

    return PrdApprovalEntity(
      workflowKey: workflowKey,
      status: status,
      approvedAt: approvedAt,
      lastEditedAt: lastEditedAt,
      sourceRunId: sourceRunId,
    );
  }

  @override
  void write(BinaryWriter writer, PrdApprovalEntity obj) {
    writer
      ..writeByte(5)
      ..writeByte(0)
      ..writeString(obj.workflowKey)
      ..writeByte(1)
      ..writeByte(obj.status.index)
      ..writeByte(2)
      ..writeBool(obj.approvedAt != null);
    if (obj.approvedAt != null) {
      writer.writeInt(obj.approvedAt!.millisecondsSinceEpoch);
    }
    writer
      ..writeByte(3)
      ..writeBool(obj.lastEditedAt != null);
    if (obj.lastEditedAt != null) {
      writer.writeInt(obj.lastEditedAt!.millisecondsSinceEpoch);
    }
    writer
      ..writeByte(4)
      ..writeBool(obj.sourceRunId != null);
    if (obj.sourceRunId != null) {
      writer.writeString(obj.sourceRunId!);
    }
  }
}
