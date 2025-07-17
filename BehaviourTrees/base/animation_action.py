"""
Generic animation action behaviour for py_trees.
"""

import py_trees
from py_trees import common
from typing import Optional


class AnimationAction(py_trees.behaviour.Behaviour):
    """Generic behaviour for playing servo animations."""
    
    def __init__(self, name: str, animation_controller, animation_name: str, looping: bool = False):
        super().__init__(name)
        self.animation_controller = animation_controller
        self.animation_name = animation_name
        self.animation_blending_out = False
        self.animation_started = False
        self.animation_finished = False
        self.animation_looping = looping
        self.blackboard = self.attach_blackboard_client(name="Animation")
        self.blackboard.register_key("current_animation", common.Access.WRITE)
        
    def setup(self, **kwargs):
        self.logger.debug(f"  {self.name} [AnimationAction::setup()]")
        
    def on_anim_finished_cb(self):
        """Callback when animation finishes."""
        self.logger.debug(f"  {self.name} [AnimationAction::on_anim_finished_cb()]")
        self.animation_finished = True
        self.blackboard.current_animation = None
        self.feedback_message = f"Animation {self.animation_name} finished"
        
    def on_blend_out_cb(self):
        """Callback when animation blending out."""
        self.logger.debug(f"  {self.name} [AnimationAction::on_blend_out_cb()]")
        self.animation_blending_out = True
        self.feedback_message = f"Animation {self.animation_name} blending out"
        
    def initialise(self):
        self.logger.debug(f"  {self.name} [AnimationAction::initialise()]")
        # Start the animation
        try:
            layer = self.animation_controller.get_layer_by_name(self.animation_name)
            if not layer and self.animation_name in self.animation_controller.available_animations:
                layer = self.animation_controller.create_layer(
                    self.animation_controller.available_animations[self.animation_name],
                    self.animation_name, 1.0, self.animation_looping, True
                )
                layer.on_start_blend_out = self.on_blend_out_cb
                layer.on_complete = self.on_anim_finished_cb
            
            self.animation_started = False
            self.animation_finished = False
            self.animation_blending_out = False
        except Exception as e:
            self.feedback_message = f"Error starting animation: {str(e)}"
        
    def update(self):
        self.logger.debug(f"  {self.name} [AnimationAction::update()]")
        # Check if animation is still playing
        try:
            layer = self.animation_controller.get_layer_by_name(self.animation_name)
            
            if layer:
                if not self.animation_started:
                    self.blackboard.current_animation = self.animation_name
                    self.feedback_message = f"Started animation: {self.animation_name}"

                    self.animation_started = True
                    self.animation_controller.animate_layer_weight(layer, 1.0, 1.0)
                    layer.play()
                else:
                    self.feedback_message = f"Animation {self.animation_name} on frame {layer.current_frame}"
            
                if self.animation_blending_out or self.animation_finished:
                    self.feedback_message = f"Animation {self.animation_name} completed or blending out to completion"
                    return common.Status.SUCCESS
                
                return common.Status.RUNNING
            else:
                self.feedback_message = f"Animation not found: {self.animation_name}"               

        except Exception as e:
            self.feedback_message = f"Error checking animation: {str(e)}"
        
        return common.Status.FAILURE
            
    def terminate(self, new_status):
        self.logger.debug(f"  {self.name} [AnimationAction::terminate()][{self.status}->{new_status}]")
        if new_status == common.Status.INVALID:
            # Stop animation if interrupted
            try:
                # Animation cleanup could be added here if needed
                pass
            except Exception as e:
                self.logger.error(f"Error stopping animation: {str(e)}")