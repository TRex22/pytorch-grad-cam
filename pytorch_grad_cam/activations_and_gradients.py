import torch

class ActivationsAndGradients:
    """ Class for extracting activations and
    registering gradients from targetted intermediate layers """

    def __init__(self, model, target_layers, reshape_transform, use_cuda: bool = False, compute_device: torch.device = None):
        self.model = model
        self.gradients = []
        self.activations = []
        self.reshape_transform = reshape_transform
        self.handles = []

        self.use_cuda = use_cuda

        # TODO: Possible clean-up here
        if compute_device:
            self.compute_device = compute_device
            self.use_cuda = True
        elif self.use_cuda:
            self.compute_device = torch.device("cuda")
        else:
            self.compute_device = torch.device("cpu")

        for target_layer in target_layers:
            self.handles.append(
                target_layer.register_forward_hook(self.save_activation))
            # Because of https://github.com/pytorch/pytorch/issues/61519,
            # we don't use backward hook to record gradients.
            self.handles.append(
                target_layer.register_forward_hook(self.save_gradient))

    def save_activation(self, module, input, output):
        activation = output

        if self.reshape_transform is not None:
            activation = self.reshape_transform(activation)

        if self.use_cuda:
            self.activations.append(activation.to(self.compute_device).detach())
        else:
            self.activations.append(activation.cpu().detach())

    def save_gradient(self, module, input, output):
        if not hasattr(output, "requires_grad") or not output.requires_grad:
            # You can only register hooks on tensor requires grad.
            return

        # Gradients are computed in reverse order
        def _store_grad(grad):
            if self.reshape_transform is not None:
                grad = self.reshape_transform(grad)

            if self.use_cuda:
                self.gradients = [grad.to(self.compute_device).detach()] + self.gradients
            else:
                self.gradients = [grad.cpu().detach()] + self.gradients

        output.register_hook(_store_grad)

    def __call__(self, x):
        for grad in self.gradients:
            del grad

        for activation in self.activations:
            del activation

        self.gradients = []
        self.activations = []

        return self.model(x)

    def release(self):
        for grad in self.gradients:
            del grad

        for activation in self.activations:
            del activation

        for handle in self.handles:
            handle.remove()
