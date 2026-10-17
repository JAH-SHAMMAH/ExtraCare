import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import BackupCard from "@/components/settings/BackupCard";

const download = vi.fn();
vi.mock("@/lib/api", () => ({ backupApi: { download: (...a: any[]) => download(...a) } }));

beforeEach(() => {
  download.mockReset();
  (URL as any).createObjectURL = vi.fn(() => "blob:x");
  (URL as any).revokeObjectURL = vi.fn();
});

describe("BackupCard", () => {
  it("asks for the password, then downloads", async () => {
    download.mockResolvedValue(new Blob(["x"]));
    render(<BackupCard />);
    fireEvent.click(screen.getByRole("button", { name: /Download backup/ }));
    const go = screen.getByRole("button", { name: "Download" });
    expect(go).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "pw" } });
    fireEvent.click(go);
    await waitFor(() => expect(download).toHaveBeenCalledWith("pw"));
    await screen.findByText("Backup downloaded.");
  });

  it("shows the server's reason when refused", async () => {
    download.mockRejectedValue({ response: { data: new Blob([JSON.stringify({ detail: "Wrong password." })]) } });
    render(<BackupCard />);
    fireEvent.click(screen.getByRole("button", { name: /Download backup/ }));
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    await screen.findByText("Wrong password.");
  });
});
