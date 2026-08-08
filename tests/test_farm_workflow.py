import unittest

from event_script.farm_workflow import FarmWorkflow, FarmWorkflowConfig


class FarmWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.config = FarmWorkflowConfig(
            initial_image="farm.png",
            entry_image_names=("yes.png", "enter.png"),
            crops_start_image="crops.png",
            crops_collection_image_names=("collect.png",),
            crops_failure_image="crop-failure.png",
            crops_confirmation_image="crop-ok.png",
            crops_failure_confirmation_image="failure-ok.png",
            cross_image_names=("farm-cross.png", "cross.png"),
            field_image_names=("shop.png", "field.png", "target.png"),
            purchase_image_names=("cart.png", "cart-ok.png", "buy.png", "ok.png", "ok.png"),
            return_image_names=("waiting-room.png", "yes.png", "special-event.png"),
        )

    def test_runs_the_complete_sequence_through_injected_operations(self):
        clicked_images = []
        clicked_any_images = []
        step_descriptions = []
        shifted_positions = []

        def run_step(description, operation):
            step_descriptions.append(description)
            return operation()

        workflow = FarmWorkflow(
            config=self.config,
            run_step=run_step,
            click_image=lambda image_name: clicked_images.append(image_name) or True,
            click_any_image=lambda image_names: clicked_any_images.append(
                tuple(image_names)
            ) or True,
            is_image_visible=lambda image_name: False,
            load_click_positions=lambda: ((10, 20),),
            shift_click_positions=lambda positions: shifted_positions.append(positions) or True,
        )

        self.assertTrue(workflow.run())
        self.assertEqual(
            clicked_images,
            [
                self.config.initial_image,
                *self.config.entry_image_names,
                self.config.crops_start_image,
                *self.config.crops_collection_image_names,
                self.config.crops_confirmation_image,
                *self.config.crops_collection_image_names,
                self.config.crops_confirmation_image,
                *self.config.field_image_names,
                *self.config.purchase_image_names,
                *self.config.return_image_names,
            ],
        )
        self.assertEqual(
            clicked_any_images,
            [self.config.cross_image_names, self.config.cross_image_names],
        )
        self.assertEqual(shifted_positions, [((10, 20),)])
        self.assertEqual(step_descriptions[0], self.config.initial_image)
        self.assertIn("Shift-click positions", step_descriptions)

    def test_waits_after_crop_collection_before_normal_confirmation(self):
        crop_events = []

        def click_image(image_name):
            if image_name in {"collect.png", "crop-ok.png"}:
                crop_events.append(image_name)
            return True

        workflow = FarmWorkflow(
            config=self.config,
            run_step=lambda description, operation: operation(),
            click_image=click_image,
            click_any_image=lambda image_names: True,
            is_image_visible=lambda image_name: False,
            load_click_positions=lambda: ((10, 20),),
            shift_click_positions=lambda positions: True,
            wait_after_crop_collection=lambda: crop_events.append("wait") or True,
        )

        self.assertTrue(workflow.run())
        self.assertEqual(
            crop_events,
            [
                "collect.png",
                "wait",
                "crop-ok.png",
                "collect.png",
                "wait",
                "crop-ok.png",
            ],
        )

    def test_waits_between_purchase_actions_only(self):
        purchase_events = []

        def click_image(image_name):
            if image_name in self.config.purchase_image_names:
                purchase_events.append(image_name)
            return True

        workflow = FarmWorkflow(
            config=self.config,
            run_step=lambda description, operation: operation(),
            click_image=click_image,
            click_any_image=lambda image_names: True,
            is_image_visible=lambda image_name: False,
            load_click_positions=lambda: ((10, 20),),
            shift_click_positions=lambda positions: True,
            wait_between_purchase_steps=lambda: purchase_events.append("wait") or True,
        )

        self.assertTrue(workflow.run())
        expected = []
        for index, image_name in enumerate(self.config.purchase_image_names):
            expected.append(image_name)
            if index < len(self.config.purchase_image_names) - 1:
                expected.append("wait")
        self.assertEqual(purchase_events, expected)

    def test_waits_before_clicking_target_field_and_before_positions(self):
        placement_events = []

        def click_image(image_name):
            if image_name in self.config.field_image_names:
                placement_events.append(image_name)
            return True

        workflow = FarmWorkflow(
            config=self.config,
            run_step=lambda description, operation: operation(),
            click_image=click_image,
            click_any_image=lambda image_names: True,
            is_image_visible=lambda image_name: False,
            load_click_positions=lambda: ((10, 20),),
            shift_click_positions=lambda positions: placement_events.append(
                "positions"
            ) or True,
            wait_before_target_field=lambda: placement_events.append("wait") or True,
        )

        self.assertTrue(workflow.run())
        self.assertEqual(
            placement_events,
            ["shop.png", "field.png", "wait", "target.png", "positions"],
        )

    def test_crop_failure_skips_crop_management_and_continues_the_flow(self):
        clicked_images = []
        clicked_any_images = []
        crop_management_skipped = []
        crop_failure_detected = []

        workflow = FarmWorkflow(
            config=self.config,
            run_step=lambda description, operation: operation(),
            click_image=lambda image_name: clicked_images.append(image_name) or True,
            click_any_image=lambda image_names: clicked_any_images.append(
                tuple(image_names)
            ) or True,
            is_image_visible=lambda image_name: image_name == self.config.crops_failure_image,
            load_click_positions=lambda: ((10, 20),),
            shift_click_positions=lambda positions: True,
            on_crop_management_skipped=lambda: crop_management_skipped.append(True),
            on_crop_failure_detected=lambda: crop_failure_detected.append(True),
        )

        self.assertTrue(workflow.run())
        self.assertEqual(crop_management_skipped, [])
        self.assertEqual(crop_failure_detected, [True])
        self.assertNotIn(
            self.config.crops_collection_image_names[0],
            clicked_images,
        )
        self.assertIn(
            self.config.crops_failure_confirmation_image,
            clicked_images,
        )
        self.assertNotIn(self.config.crops_confirmation_image, clicked_images)
        self.assertEqual(
            clicked_any_images,
            [self.config.cross_image_names, self.config.cross_image_names],
        )
        self.assertIn(self.config.field_image_names[0], clicked_images)
        self.assertIn(self.config.return_image_names[-1], clicked_images)


    def test_crop_failure_detected_after_collection_uses_failure_confirmation(self):
        clicked_images = []
        clicked_any_images = []
        crop_failure_detected = []

        workflow = FarmWorkflow(
            config=self.config,
            run_step=lambda description, operation: operation(),
            click_image=lambda image_name: clicked_images.append(image_name) or True,
            click_any_image=lambda image_names: clicked_any_images.append(
                tuple(image_names)
            ) or True,
            is_image_visible=lambda image_name: False,
            wait_for_crop_result=lambda image_names: (
                self.config.crops_failure_image
            ),
            load_click_positions=lambda: ((10, 20),),
            shift_click_positions=lambda positions: True,
            on_crop_failure_detected=lambda: crop_failure_detected.append(True),
        )

        self.assertTrue(workflow.run())
        self.assertEqual(crop_failure_detected, [True])
        self.assertIn(
            self.config.crops_collection_image_names[0],
            clicked_images,
        )
        self.assertIn(
            self.config.crops_failure_confirmation_image,
            clicked_images,
        )
        self.assertNotIn(self.config.crops_confirmation_image, clicked_images)
        self.assertEqual(
            clicked_any_images,
            [self.config.cross_image_names, self.config.cross_image_names],
        )


    def test_failed_crop_collection_skips_to_field_placement(self):
        clicked_images = []
        clicked_any_images = []
        crop_management_skipped = []

        def click_image(image_name):
            clicked_images.append(image_name)
            return image_name != self.config.crops_collection_image_names[0]

        workflow = FarmWorkflow(
            config=self.config,
            run_step=lambda description, operation: operation(),
            click_image=click_image,
            click_any_image=lambda image_names: clicked_any_images.append(
                tuple(image_names)
            ) or True,
            is_image_visible=lambda image_name: False,
            load_click_positions=lambda: ((10, 20),),
            shift_click_positions=lambda positions: True,
            on_crop_management_skipped=lambda: crop_management_skipped.append(True),
        )

        self.assertTrue(workflow.run())
        self.assertEqual(crop_management_skipped, [True])
        self.assertEqual(
            clicked_any_images,
            [self.config.cross_image_names, self.config.cross_image_names],
        )
        self.assertIn(self.config.field_image_names[0], clicked_images)
        self.assertIn(self.config.return_image_names[-1], clicked_images)


if __name__ == "__main__":
    unittest.main()
