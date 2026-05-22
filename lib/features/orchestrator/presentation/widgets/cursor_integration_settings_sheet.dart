import 'dart:async';
import 'dart:math';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:pulse_ai/core/service/external_url_opener.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/cursor_integration_remove_confirm_dialog.dart';
import 'package:pulse_ai/shared/theme/pulse_button_styles.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';

Future<void> showCursorIntegrationSettingsSheet(BuildContext context) {
  final CursorConnectionCubit connectionCubit = context
      .read<CursorConnectionCubit>();
  final MaterialLocalizations loc = MaterialLocalizations.of(context);
  return showGeneralDialog<void>(
    context: context,
    barrierDismissible: true,
    barrierLabel: loc.modalBarrierDismissLabel,
    barrierColor: Colors.transparent,
    pageBuilder:
        (
          BuildContext dialogContext,
          Animation<double> animation,
          Animation<double> secondaryAnimation,
        ) {
          return BlocProvider<CursorConnectionCubit>.value(
            value: connectionCubit,
            child: const _CursorIntegrationSettingsSheetPage(),
          );
        },
  );
}

final class _CursorIntegrationSettingsSheetPage extends StatefulWidget {
  const _CursorIntegrationSettingsSheetPage();

  @override
  State<_CursorIntegrationSettingsSheetPage> createState() =>
      _CursorIntegrationSettingsSheetPageState();
}

final class _CursorIntegrationSettingsSheetPageState
    extends State<_CursorIntegrationSettingsSheetPage> {
  late final TextEditingController _apiKeyController;

  @override
  void initState() {
    super.initState();
    _apiKeyController = TextEditingController();
    _apiKeyController.addListener(_onDraftChanged);
  }

  @override
  void dispose() {
    _apiKeyController.removeListener(_onDraftChanged);
    _apiKeyController.dispose();
    context.read<CursorConnectionCubit>().resetSettingsSession();
    super.dispose();
  }

  void _onDraftChanged() {
    context.read<CursorConnectionCubit>().onDraftCredentialChanged();
  }

  void _closeSheet(BuildContext context) {
    _apiKeyController.clear();
    context.read<CursorConnectionCubit>().resetSettingsSession();
    Navigator.of(context).pop();
  }

  Future<void> _onRemovePressed(BuildContext context) async {
    final bool? confirmed = await CursorIntegrationRemoveConfirmDialog.show(
      context,
    );
    if (confirmed != true || !context.mounted) {
      return;
    }

    await context.read<CursorConnectionCubit>().removeCredential();
    if (!context.mounted) {
      return;
    }
    _closeSheet(context);
  }

  InputDecoration _outlineDecoration(BuildContext context, {String? hint}) {
    final TextTheme tt = Theme.of(context).textTheme;
    return InputDecoration(
      hintText: hint,
      filled: true,
      fillColor: PulseColors.surfaceContainerLowest,
      hintStyle: tt.bodyMedium?.copyWith(color: PulseColors.outline),
      floatingLabelBehavior: FloatingLabelBehavior.never,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(PulseRadii.actionButton),
        borderSide: const BorderSide(color: PulseColors.outlineVariant),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(PulseRadii.actionButton),
        borderSide: const BorderSide(color: PulseColors.outlineVariant),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(PulseRadii.actionButton),
        borderSide: const BorderSide(color: PulseColors.primary),
      ),
      contentPadding: PulseInsets.sidebarHeader,
    );
  }

  Widget _formLabel(TextTheme tt, String text) {
    return Text(
      text,
      style: tt.labelMedium?.copyWith(color: PulseColors.onSurfaceVariant),
    );
  }

  bool _hasStoredCredential(CursorConnectionStatus status) {
    return status == CursorConnectionStatus.connected ||
        status == CursorConnectionStatus.failure;
  }

  bool _showsConfiguredIndicator(
    CursorConnectionState state,
    String draftText,
  ) {
    return _hasStoredCredential(state.status) &&
        draftText.trim().isEmpty &&
        !state.isDraftTestPassed;
  }

  @override
  Widget build(BuildContext context) {
    final TextTheme tt = Theme.of(context).textTheme;
    final double viewHeight = MediaQuery.sizeOf(context).height;
    final double maxDialogHeight = min(viewHeight * 0.92, 560);

    return SafeArea(
      child: Material(
        color: Colors.transparent,
        child: Stack(
          fit: StackFit.expand,
          children: <Widget>[
            Positioned.fill(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTap: () => _closeSheet(context),
                child: ClipRect(
                  child: BackdropFilter(
                    filter: ImageFilter.blur(
                      sigmaX: PulseDimensions.modalBackdropBlurSigma,
                      sigmaY: PulseDimensions.modalBackdropBlurSigma,
                    ),
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        color: PulseColors.modalBarrierScrim.withValues(
                          alpha: 0.55,
                        ),
                      ),
                      child: const SizedBox.expand(),
                    ),
                  ),
                ),
              ),
            ),
            Center(
              child: Semantics(
                scopesRoute: true,
                namesRoute: true,
                label: OrchestratorStrings.cursorSettingsModalSemantics,
                child: Material(
                  color: PulseColors.surfaceContainer,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(
                      PulseRadii.actionButton,
                    ),
                    side: const BorderSide(color: PulseColors.outlineVariant),
                  ),
                  elevation: 12,
                  child: ConstrainedBox(
                    constraints: BoxConstraints(
                      maxWidth: PulseDimensions.modalMaxWidth,
                      maxHeight: maxDialogHeight,
                    ),
                    child: BlocListener<CursorConnectionCubit, CursorConnectionState>(
                      listenWhen:
                          (
                            CursorConnectionState previous,
                            CursorConnectionState current,
                          ) =>
                              previous.settingsOperation ==
                                  CursorSettingsOperationStatus.saving &&
                              current.settingsOperation ==
                                  CursorSettingsOperationStatus.idle &&
                              current.status ==
                                  CursorConnectionStatus.connected,
                      listener:
                          (BuildContext context, CursorConnectionState state) {
                            _apiKeyController.clear();
                          },
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          DecoratedBox(
                            decoration: const BoxDecoration(
                              color: PulseColors.surfaceContainerHigh,
                              border: Border(
                                bottom: BorderSide(
                                  color: PulseColors.outlineVariant,
                                ),
                              ),
                            ),
                            child: Padding(
                              padding: PulseInsets.ctaCard,
                              child: Row(
                                children: <Widget>[
                                  Expanded(
                                    child: Text(
                                      OrchestratorStrings
                                          .cursorSettingsModalTitle,
                                      style: tt.headlineSmall?.copyWith(
                                        color: PulseColors.primary,
                                      ),
                                    ),
                                  ),
                                  IconButton(
                                    visualDensity: VisualDensity.compact,
                                    tooltip: OrchestratorStrings
                                        .cursorSettingsCloseSemantics,
                                    onPressed: () => _closeSheet(context),
                                    icon: const Icon(
                                      Icons.close,
                                      color: PulseColors.onSurfaceVariant,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                          Flexible(
                            child: ListView(
                              shrinkWrap: true,
                              physics: const ClampingScrollPhysics(),
                              padding: PulseInsets.modalFormPadding,
                              children: <Widget>[
                                ValueListenableBuilder<TextEditingValue>(
                                  valueListenable: _apiKeyController,
                                  builder:
                                      (
                                        BuildContext context,
                                        TextEditingValue draftValue,
                                        Widget? child,
                                      ) {
                                        return BlocBuilder<
                                          CursorConnectionCubit,
                                          CursorConnectionState
                                        >(
                                          buildWhen:
                                              (
                                                CursorConnectionState previous,
                                                CursorConnectionState current,
                                              ) =>
                                                  previous.status !=
                                                      current.status ||
                                                  previous.isDraftTestPassed !=
                                                      current
                                                          .isDraftTestPassed ||
                                                  previous.settingsFeedbackMessageKey !=
                                                      current
                                                          .settingsFeedbackMessageKey ||
                                                  previous.settingsOperation !=
                                                      current.settingsOperation,
                                          builder:
                                              (
                                                BuildContext context,
                                                CursorConnectionState state,
                                              ) {
                                                final String draft =
                                                    draftValue.text;
                                                final bool operationInProgress =
                                                    state.settingsOperation !=
                                                    CursorSettingsOperationStatus
                                                        .idle;
                                                final bool draftNonEmpty = draft
                                                    .trim()
                                                    .isNotEmpty;
                                                final bool canTest =
                                                    draftNonEmpty &&
                                                    !operationInProgress;
                                                final bool canSave =
                                                    state.isDraftTestPassed &&
                                                    !operationInProgress;
                                                final bool canRemove =
                                                    _hasStoredCredential(
                                                      state.status,
                                                    ) &&
                                                    !operationInProgress;
                                                final bool showConfigured =
                                                    _showsConfiguredIndicator(
                                                      state,
                                                      draft,
                                                    );
                                                final String? feedback = state
                                                    .settingsFeedbackMessageKey;

                                                return Column(
                                                  crossAxisAlignment:
                                                      CrossAxisAlignment
                                                          .stretch,
                                                  children: <Widget>[
                                                    if (showConfigured) ...<
                                                      Widget
                                                    >[
                                                      DecoratedBox(
                                                        decoration: BoxDecoration(
                                                          color: PulseColors
                                                              .surfaceContainerLow,
                                                          borderRadius:
                                                              BorderRadius.circular(
                                                                PulseRadii
                                                                    .actionButton,
                                                              ),
                                                          border: const Border.fromBorderSide(
                                                            BorderSide(
                                                              color: PulseColors
                                                                  .outlineVariant,
                                                            ),
                                                          ),
                                                        ),
                                                        child: Padding(
                                                          padding: PulseInsets
                                                              .ctaCard,
                                                          child: Row(
                                                            children: <Widget>[
                                                              const Icon(
                                                                Icons
                                                                    .check_circle_outline,
                                                                color:
                                                                    PulseColors
                                                                        .primary,
                                                                size: PulseDimensions
                                                                    .workflowInfoBannerIconSize,
                                                              ),
                                                              const SizedBox(
                                                                width: PulseDimensions
                                                                    .sectionGapSm,
                                                              ),
                                                              Expanded(
                                                                child: Text(
                                                                  OrchestratorStrings
                                                                      .cursorSettingsConfiguredStatus,
                                                                  style: tt
                                                                      .bodyMedium
                                                                      ?.copyWith(
                                                                        color: PulseColors
                                                                            .onSurface,
                                                                      ),
                                                                ),
                                                              ),
                                                            ],
                                                          ),
                                                        ),
                                                      ),
                                                      const SizedBox(
                                                        height: PulseDimensions
                                                            .sectionGapLg,
                                                      ),
                                                    ],
                                                    _formLabel(
                                                      tt,
                                                      OrchestratorStrings
                                                          .cursorSettingsApiKeyLabel,
                                                    ),
                                                    const SizedBox(
                                                      height: PulseDimensions
                                                          .sectionGapSm,
                                                    ),
                                                    Semantics(
                                                      label: OrchestratorStrings
                                                          .cursorSettingsApiKeyFieldSemantics,
                                                      textField: true,
                                                      child: TextField(
                                                        controller:
                                                            _apiKeyController,
                                                        obscureText: true,
                                                        autocorrect: false,
                                                        enableSuggestions:
                                                            false,
                                                        style: tt.labelLarge
                                                            ?.copyWith(
                                                              color: PulseColors
                                                                  .onSurface,
                                                            ),
                                                        decoration: _outlineDecoration(
                                                          context,
                                                          hint: OrchestratorStrings
                                                              .cursorSettingsApiKeyHint,
                                                        ),
                                                      ),
                                                    ),
                                                    const SizedBox(
                                                      height: PulseDimensions
                                                          .sectionGapSm,
                                                    ),
                                                    Text(
                                                      OrchestratorStrings
                                                          .cursorSettingsHelperText,
                                                      style: tt.bodySmall
                                                          ?.copyWith(
                                                            color: PulseColors
                                                                .onSurfaceVariant,
                                                          ),
                                                    ),
                                                    if (feedback !=
                                                        null) ...<Widget>[
                                                      const SizedBox(
                                                        height: PulseDimensions
                                                            .sectionGapSm,
                                                      ),
                                                      Text(
                                                        feedback,
                                                        style: tt.bodySmall
                                                            ?.copyWith(
                                                              color: Theme.of(
                                                                context,
                                                              ).colorScheme.error,
                                                            ),
                                                      ),
                                                    ],
                                                    const SizedBox(
                                                      height: PulseDimensions
                                                          .sectionGapMd,
                                                    ),
                                                    Semantics(
                                                      button: true,
                                                      label: OrchestratorStrings
                                                          .cursorSettingsDocumentationLinkSemantics,
                                                      child: TextButton.icon(
                                                        onPressed:
                                                            operationInProgress
                                                            ? null
                                                            : () {
                                                                unawaited(
                                                                  openExternalUrl(
                                                                    Uri.parse(
                                                                      OrchestratorStrings
                                                                          .cursorSettingsDocumentationUrl,
                                                                    ),
                                                                  ),
                                                                );
                                                              },
                                                        icon: const Icon(
                                                          Icons.open_in_new,
                                                          size: PulseDimensions
                                                              .sidebarTreeIconSize,
                                                        ),
                                                        label: const Text(
                                                          OrchestratorStrings
                                                              .cursorSettingsDocumentationLinkLabel,
                                                        ),
                                                      ),
                                                    ),
                                                    const SizedBox(
                                                      height: PulseDimensions
                                                          .sectionGapLg,
                                                    ),
                                                    Row(
                                                      children: <Widget>[
                                                        Expanded(
                                                          child: Semantics(
                                                            button: true,
                                                            label: OrchestratorStrings
                                                                .cursorSettingsTestButtonSemantics,
                                                            child: OutlinedButton(
                                                              onPressed: canTest
                                                                  ? () {
                                                                      unawaited(
                                                                        context
                                                                            .read<
                                                                              CursorConnectionCubit
                                                                            >()
                                                                            .testDraftCredential(
                                                                              draft.trim(),
                                                                            ),
                                                                      );
                                                                    }
                                                                  : null,
                                                              style: PulseButtonStyles.outlinedAction(
                                                                foregroundColor:
                                                                    PulseColors
                                                                        .primary,
                                                                backgroundColor:
                                                                    PulseColors
                                                                        .surfaceContainerLowest,
                                                                borderColor:
                                                                    PulseColors
                                                                        .outlineVariant,
                                                                textStyle:
                                                                    tt.labelLarge ??
                                                                    const TextStyle(),
                                                              ),
                                                              child:
                                                                  state.settingsOperation ==
                                                                      CursorSettingsOperationStatus
                                                                          .testing
                                                                  ? const SizedBox(
                                                                      width: PulseDimensions
                                                                          .sidebarTreeIconSize,
                                                                      height: PulseDimensions
                                                                          .sidebarTreeIconSize,
                                                                      child: CircularProgressIndicator(
                                                                        strokeWidth:
                                                                            2,
                                                                        color: PulseColors
                                                                            .primary,
                                                                      ),
                                                                    )
                                                                  : const Text(
                                                                      OrchestratorStrings
                                                                          .cursorSettingsTestButton,
                                                                    ),
                                                            ),
                                                          ),
                                                        ),
                                                        const SizedBox(
                                                          width: PulseDimensions
                                                              .sectionGapMd,
                                                        ),
                                                        Expanded(
                                                          child: Semantics(
                                                            button: true,
                                                            label: OrchestratorStrings
                                                                .cursorSettingsSaveButtonSemantics,
                                                            child: FilledButton(
                                                              onPressed: canSave
                                                                  ? () {
                                                                      unawaited(
                                                                        context
                                                                            .read<
                                                                              CursorConnectionCubit
                                                                            >()
                                                                            .saveDraftCredential(
                                                                              draft.trim(),
                                                                            ),
                                                                      );
                                                                    }
                                                                  : null,
                                                              style:
                                                                  PulseButtonStyles.filledPrimary(
                                                                    context,
                                                                  ),
                                                              child:
                                                                  state.settingsOperation ==
                                                                      CursorSettingsOperationStatus
                                                                          .saving
                                                                  ? const SizedBox(
                                                                      width: PulseDimensions
                                                                          .sidebarTreeIconSize,
                                                                      height: PulseDimensions
                                                                          .sidebarTreeIconSize,
                                                                      child: CircularProgressIndicator(
                                                                        strokeWidth:
                                                                            2,
                                                                        color: PulseColors
                                                                            .onPrimary,
                                                                      ),
                                                                    )
                                                                  : const Text(
                                                                      OrchestratorStrings
                                                                          .cursorSettingsSaveButton,
                                                                    ),
                                                            ),
                                                          ),
                                                        ),
                                                      ],
                                                    ),
                                                    const SizedBox(
                                                      height: PulseDimensions
                                                          .sectionGapMd,
                                                    ),
                                                    Semantics(
                                                      button: true,
                                                      label: OrchestratorStrings
                                                          .cursorSettingsRemoveButtonSemantics,
                                                      child: TextButton(
                                                        onPressed: canRemove
                                                            ? () => unawaited(
                                                                _onRemovePressed(
                                                                  context,
                                                                ),
                                                              )
                                                            : null,
                                                        style:
                                                            TextButton.styleFrom(
                                                              foregroundColor:
                                                                  Theme.of(
                                                                        context,
                                                                      )
                                                                      .colorScheme
                                                                      .error,
                                                            ),
                                                        child:
                                                            state.settingsOperation ==
                                                                CursorSettingsOperationStatus
                                                                    .removing
                                                            ? SizedBox(
                                                                width: PulseDimensions
                                                                    .sidebarTreeIconSize,
                                                                height: PulseDimensions
                                                                    .sidebarTreeIconSize,
                                                                child: CircularProgressIndicator(
                                                                  strokeWidth:
                                                                      2,
                                                                  color: Theme.of(
                                                                    context,
                                                                  ).colorScheme.error,
                                                                ),
                                                              )
                                                            : const Text(
                                                                OrchestratorStrings
                                                                    .cursorSettingsRemoveButton,
                                                              ),
                                                      ),
                                                    ),
                                                  ],
                                                );
                                              },
                                        );
                                      },
                                ),
                              ],
                            ),
                          ),
                          DecoratedBox(
                            decoration: const BoxDecoration(
                              color: PulseColors.surfaceContainerLow,
                              border: Border(
                                top: BorderSide(
                                  color: PulseColors.outlineVariant,
                                ),
                              ),
                            ),
                            child: Padding(
                              padding: PulseInsets.modalFooterPadding,
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.end,
                                children: <Widget>[
                                  TextButton(
                                    onPressed: () => _closeSheet(context),
                                    style: TextButton.styleFrom(
                                      foregroundColor:
                                          PulseColors.onSurfaceVariant,
                                    ),
                                    child: const Text(
                                      OrchestratorStrings
                                          .cursorSettingsCancelButton,
                                    ),
                                  ),
                                ],
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
          ],
        ),
      ),
    );
  }
}
