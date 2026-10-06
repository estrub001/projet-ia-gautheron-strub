import torch

print(f"PyTorch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")

if torch.cuda.is_available():
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print(f"CUDA version: {torch.version.cuda}")

    x = torch.randn(1000, 1000, device="cuda")
    print(f"Matmul OK: {(x @ x).shape}")
