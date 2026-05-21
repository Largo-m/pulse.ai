import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/cursor_connection_banner_policy.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class CursorConnectionBanner extends StatelessWidget {
  const CursorConnectionBanner({super.key, this.onOpenSettings});

  final VoidCallback? onOpenSettings;

  @override
  Widget build(BuildContext context) {
    return BlocBuilder<CursorConnectionCubit, CursorConnectionState>(
      buildWhen:
          (CursorConnectionState previous, CursorConnectionState current) =>
              previous.status != current.status ||
              previous.remediationMessage != current.remediationMessage,
      builder: (BuildContext context, CursorConnectionState state) {
        if (!CursorConnectionBannerPolicy.shouldShow(state.status)) {
          return const SizedBox.shrink();
        }

        final TextTheme textTheme = Theme.of(context).textTheme;
        final String message = CursorConnectionBannerPolicy.remediationMessage(
          state,
        );

        return Semantics(
          container: true,
          label: OrchestratorStrings.cursorConnectionBannerSemantics,
          child: DecoratedBox(
            decoration: BoxDecoration(
              color: PulseColors.secondary.withValues(
                alpha: PulseDimensions.workflowInfoBannerBorderAlpha,
              ),
              border: Border(
                bottom: BorderSide(
                  color: PulseColors.outlineVariant.withValues(
                    alpha: PulseDimensions.workflowInfoBannerBorderAlpha,
                  ),
                ),
              ),
            ),
            child: Padding(
              padding: PulseInsets.breadcrumbHorizontal,
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(
                    maxWidth: PulseDimensions.workflowStepperMaxWidth,
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      vertical: PulseDimensions.sectionGapSm,
                    ),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        const Icon(
                          Icons.cloud_off_outlined,
                          size: PulseDimensions.workflowInfoBannerIconSize,
                          color: PulseColors.secondary,
                        ),
                        const SizedBox(width: PulseDimensions.sectionGapSm),
                        Expanded(
                          child: Text(
                            message,
                            style: textTheme.bodyMedium?.copyWith(
                              color: PulseColors.onSurface,
                            ),
                          ),
                        ),
                        const SizedBox(width: PulseDimensions.sectionGapMd),
                        Semantics(
                          button: true,
                          label: OrchestratorStrings.cursorConnectionBannerCta,
                          child: TextButton(
                            onPressed: onOpenSettings,
                            child: const Text(
                              OrchestratorStrings.cursorConnectionBannerCta,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}
