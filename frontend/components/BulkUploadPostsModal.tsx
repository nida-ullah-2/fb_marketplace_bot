"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import {
  Upload,
  Download,
  FileText,
  CheckCircle,
  AlertCircle,
  Info,
  X,
} from "lucide-react";
import { accountsAPI } from "@/lib/api";

interface BulkUploadPostsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  onToast: (type: "success" | "error", message: string) => void;
}

interface FacebookAccount {
  id: number;
  email: string;
  session_exists: boolean;
}

interface UploadError {
  row: number;
  error: string;
}

export default function BulkUploadPostsModal({
  isOpen,
  onClose,
  onSuccess,
  onToast,
}: BulkUploadPostsModalProps) {
  const [accounts, setAccounts] = useState<FacebookAccount[]>([]);
  const [selectedAccounts, setSelectedAccounts] = useState<number[]>([]);
  const [txtFile, setTxtFile] = useState<File | null>(null);
  const [imageFiles, setImageFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{
    success: boolean;
    message: string;
    stats?: {
      success_count: number;
      error_count: number;
      num_posts: number;
      num_accounts: number;
    };
    errors?: UploadError[];
    additional_errors?: number;
  } | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchAccounts();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const fetchAccounts = async () => {
    try {
      const response = await accountsAPI.list();
      setAccounts(response.data);
    } catch (err) {
      console.error("Failed to fetch accounts:", err);
      onToast("error", "Failed to load accounts");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith(".txt")) {
        onToast("error", "Please select a TXT file");
        return;
      }
      setTxtFile(file);
      setUploadResult(null);
    }
  };

  const handleImageFilesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      const imageFilesArray = Array.from(files);
      // Filter only image files
      const validImages = imageFilesArray.filter((file) =>
        file.type.startsWith("image/")
      );
      if (validImages.length !== imageFilesArray.length) {
        onToast("error", "Some files are not valid images");
      }
      setImageFiles(validImages);
      setUploadResult(null);
    }
  };

  const handleAccountToggle = (accountId: number) => {
    setSelectedAccounts((prev) => {
      if (prev.includes(accountId)) {
        return prev.filter((id) => id !== accountId);
      } else {
        return [...prev, accountId];
      }
    });
  };

  const handleSelectAllAccounts = () => {
    if (selectedAccounts.length === accounts.length) {
      setSelectedAccounts([]);
    } else {
      setSelectedAccounts(accounts.map((acc) => acc.id));
    }
  };

  const downloadSampleTXT = () => {
    const txtContent = `# Sample 3-line format (title, description, price)
iPhone 13 Pro
Excellent condition iPhone 13 Pro with 256GB storage. Includes original box and accessories.
699

Samsung 55 inch TV
Brand new 55 inch 4K Smart TV with HDR support. Never used.
450

Gaming Laptop
High performance gaming laptop with RTX 3060 graphics card. Perfect for gaming and content creation.
1200

# Sample single-line compact format (title | min-max)
Queen , King and sigle size mattresses and box spring and bed frames and metal frames | 10-50

# Notes:
# - Single-line compact format: Title | min-max (min and max are integer values).
# - If you upload multiple images with a single-line product, the product will be replicated for each image and a random integer price will be chosen from the range.`;

    const blob = new Blob([txtContent], { type: "text/plain" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sample_bulk_upload.txt";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!txtFile) {
      onToast("error", "Please select a TXT file");
      return;
    }

    if (selectedAccounts.length === 0) {
      onToast("error", "Please select at least one account");
      return;
    }

    setLoading(true);
    setUploadResult(null);

    try {
      // Create FormData for multipart upload
      const formData = new FormData();
      formData.append("txt_file", txtFile);

      // Add selected account IDs
      selectedAccounts.forEach((accountId) => {
        formData.append("account_ids[]", accountId.toString());
      });

      // Add image files if any
      imageFiles.forEach((imageFile) => {
        formData.append("images", imageFile);
      });

      // Call API with images support
      const API_URL =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
      const token = localStorage.getItem("token");

      const response = await fetch(
        `${API_URL}/posts/bulk-upload-with-images/`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Upload failed");
      }

      setUploadResult({
        success: true,
        message: data.message,
        stats: data.stats,
        errors: data.errors,
        additional_errors: data.additional_errors,
      });

      onToast("success", data.message);

      // Reset form
      setTxtFile(null);
      setImageFiles([]);
      setSelectedAccounts([]);

      // Call success callback to refresh posts list
      onSuccess();

      // Close modal after a short delay
      setTimeout(() => {
        onClose();
      }, 2000);
    } catch (err) {
      const error = err as Error;
      const errorMessage = error.message || "Failed to upload TXT file";
      setUploadResult({
        success: false,
        message: errorMessage,
      });
      onToast("error", errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setTxtFile(null);
    setSelectedAccounts([]);
    setUploadResult(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200 sticky top-0 bg-white z-10">
          <h2 className="text-2xl font-bold text-gray-900">
            📦 Create Multiple Posts via TXT File
          </h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close modal"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Instructions */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-blue-800 space-y-2">
                  <p className="font-medium">Bulk upload via TXT file</p>
                  <ol className="list-decimal ml-4 space-y-1">
                    <li>Prepare a TXT file containing your product entries (formats shown below).</li>
                    <li>Optionally upload product images. If provided, images must be in the same order as TXT entries.</li>
                    <li>Select one or more Facebook accounts; the system will create posts for each selected account.</li>
                  </ol>
                  <p className="font-medium mt-3">Supported TXT formats</p>
                  <div className="bg-blue-100 p-2 rounded font-mono text-xs overflow-x-auto whitespace-pre-wrap">
                    {/* 3-line format example */}
                    Sofa
                    <br />
                    Comfortable three-seater sofa, great condition.
                    <br />
                    250
                    <br />
                    <br />
                    {/* single-line compact example */}
                    Blue sofa | 100-250
                  </div>
                    <p className="text-xs mt-2">
                      <strong>Note:</strong> This interface supports two TXT formats: the traditional 3-line format (title, description, price) or the compact single-line format <code>Title | min-max</code> (for example, <code>Blue sofa | 100-250</code>).
                    </p>
                    <p className="text-xs mt-1">
                      When using the compact <code>min-max</code> format, the system will select a random integer price within the specified range for each created post. If you provide a single product line and upload multiple images, the product will be duplicated for each image (one post per image).
                    </p>
                  <button
                    type="button"
                    onClick={downloadSampleTXT}
                    className="flex items-center gap-2 text-blue-600 hover:text-blue-800 font-medium mt-2"
                  >
                    <Download size={16} />
                    Download Sample TXT
                  </button>
                </div>
              </div>
            </div>

            {/* Account Selection */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-gray-700">
                  Select Facebook Accounts{" "}
                  <span className="text-red-500">*</span>
                </label>
                {accounts.length > 0 && (
                  <button
                    type="button"
                    onClick={handleSelectAllAccounts}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                  >
                    {selectedAccounts.length === accounts.length
                      ? "Deselect All"
                      : "Select All"}
                  </button>
                )}
              </div>

              {accounts.length === 0 ? (
                <p className="text-sm text-gray-500 p-3 bg-gray-50 rounded-lg">
                  No accounts available. Please add an account first.
                </p>
              ) : (
                <div className="border border-gray-300 rounded-lg divide-y divide-gray-200 max-h-48 overflow-y-auto">
                  {accounts.map((account) => (
                    <label
                      key={account.id}
                      className="flex items-center p-3 hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={selectedAccounts.includes(account.id)}
                        onChange={() => handleAccountToggle(account.id)}
                        className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      />
                      <span className="ml-3 text-sm text-gray-900">
                        {account.email}
                      </span>
                      {account.session_exists ? (
                        <CheckCircle
                          size={16}
                          className="ml-auto text-green-600"
                        />
                      ) : (
                        <AlertCircle
                          size={16}
                          className="ml-auto text-red-600"
                        />
                      )}
                    </label>
                  ))}
                </div>
              )}
              <p className="mt-2 text-xs text-gray-500">
                Select one or more accounts. Posts will be created for ALL
                selected accounts.
              </p>
            </div>

            {/* File Upload */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                TXT File <span className="text-red-500">*</span>
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 transition-colors">
                <input
                  type="file"
                  accept=".txt"
                  onChange={handleFileChange}
                  className="hidden"
                  id="txt-upload"
                />
                <label
                  htmlFor="txt-upload"
                  className="cursor-pointer flex flex-col items-center"
                >
                  {txtFile ? (
                    <>
                      <FileText className="h-12 w-12 text-green-600 mb-2" />
                      <p className="text-sm font-medium text-gray-900">
                        {txtFile.name}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Click to change file
                      </p>
                    </>
                  ) : (
                    <>
                      <Upload className="h-12 w-12 text-gray-400 mb-2" />
                      <p className="text-sm font-medium text-gray-900">
                        Click to select a file
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        or drag and drop your .txt file here
                      </p>
                    </>
                  )}
                </label>
              </div>
              <div className="mt-2 text-xs text-gray-500">
                <div>Upload a TXT file. Supported formats:</div>
                <ul className="list-disc ml-4 mt-1 text-xs">
                  <li>3-line format (title, description, price)</li>
                  <li>
                    Single-line compact format: <code>Title | min-max</code>
                    (e.g. <code>Chair | 10-40</code>)
                  </li>
                </ul>
              </div>
            </div>

            {/* Image Files Upload (NEW!) */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Product Images <span className="text-gray-400">(Optional)</span>
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-blue-500 transition-colors">
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleImageFilesChange}
                  className="hidden"
                  id="images-upload"
                />
                <label
                  htmlFor="images-upload"
                  className="cursor-pointer flex flex-col items-center"
                >
                  {imageFiles.length > 0 ? (
                    <>
                      <CheckCircle className="h-10 w-10 text-green-600 mb-2" />
                      <p className="text-sm font-medium text-gray-900">
                        {imageFiles.length} image(s) selected
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        {imageFiles.map((f) => f.name).join(", ")}
                      </p>
                      <p className="text-xs text-blue-600 mt-2">
                        Click to add more or change images
                      </p>
                    </>
                  ) : (
                    <>
                      <Upload className="h-10 w-10 text-gray-400 mb-2" />
                      <p className="text-sm font-medium text-gray-900">
                        Click to select images
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Select multiple images at once
                      </p>
                    </>
                  )}
                </label>
              </div>
              <div className="mt-2 bg-blue-50 border border-blue-200 rounded-lg p-3">
                <p className="text-xs text-blue-800">
                  💡 <strong>Tip:</strong> Select images in the SAME ORDER as
                  your TXT rows. The app will automatically match them: 1st
                  image → 1st product, 2nd image → 2nd product, etc. If you
                  provide a single-line product and multiple images, the
                  product will be replicated for each image.
                </p>
              </div>
            </div>

            {/* Upload Result */}
            {uploadResult && (
              <div
                className={`border rounded-lg p-4 ${
                  uploadResult.success
                    ? "bg-green-50 border-green-200"
                    : "bg-red-50 border-red-200"
                }`}
              >
                <div className="flex items-start gap-2">
                  {uploadResult.success ? (
                    <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                  ) : (
                    <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                  )}
                  <div className="flex-1">
                    <p
                      className={`text-sm font-medium ${
                        uploadResult.success ? "text-green-800" : "text-red-800"
                      }`}
                    >
                      {uploadResult.message}
                    </p>
                    {uploadResult.stats && (
                      <div className="mt-2 text-xs text-gray-700">
                        <p>
                          • {uploadResult.stats.num_posts} post(s) ×{" "}
                          {uploadResult.stats.num_accounts} account(s) ={" "}
                          {uploadResult.stats.success_count} total posts created
                        </p>
                        {uploadResult.stats.error_count > 0 && (
                          <p className="text-red-600">
                            • {uploadResult.stats.error_count} error(s)
                            encountered
                          </p>
                        )}
                      </div>
                    )}
                    {uploadResult.errors && uploadResult.errors.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {uploadResult.errors.map((err, idx) => (
                          <p key={idx} className="text-xs text-red-700">
                            Row {err.row}: {err.error}
                          </p>
                        ))}
                        {uploadResult.additional_errors &&
                          uploadResult.additional_errors > 0 && (
                            <p className="text-xs text-red-700 font-medium">
                              ...and {uploadResult.additional_errors} more
                              error(s)
                            </p>
                          )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* How it Works */}
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-yellow-600 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-yellow-800">
                  <p className="font-medium mb-2">📊 How It Works:</p>
                  <div className="space-y-2">
                    <p>
                      <strong>1.</strong> Upload TXT file with products (3 lines
                      each: title, description, price)
                    </p>
                    <p>
                      <strong>2.</strong> Upload images in the SAME ORDER as
                      products
                    </p>
                    <p>
                      <strong>3.</strong> Select accounts to post to
                    </p>
                    <p>
                      <strong>4.</strong> App matches automatically: 1st image →
                      1st product, 2nd → 2nd, etc.
                    </p>
                    <p>
                      <strong>5.</strong> Posts created for EACH account!
                    </p>
                  </div>
                  <div className="mt-3 pt-3 border-t border-yellow-300">
                    <p className="font-medium">Example:</p>
                    <p className="text-xs mt-1">
                      TXT: 3 products (iPhone, TV, Laptop)
                      <br />
                      Images: 3 images (in same order)
                      <br />
                      Selected: 2 accounts (A, B)
                      <br />
                      <strong>Result: 6 total posts</strong> (3 × 2)
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 pt-4 border-t">
              <Button
                type="button"
                variant="outline"
                onClick={handleClose}
                disabled={loading}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={loading || !txtFile}>
                {loading ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                    Uploading...
                  </>
                ) : (
                  <>
                    <Upload size={20} className="mr-2" />
                    Upload TXT
                  </>
                )}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
