Set-StrictMode -Version Latest

if ($null -eq ('ProofLoop.QwenCredentialNative' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

namespace ProofLoop {
    public static class QwenCredentialNative {
        private const int CRED_TYPE_GENERIC = 1;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct CREDENTIAL {
            public int Flags;
            public int Type;
            public IntPtr TargetName;
            public IntPtr Comment;
            public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
            public int CredentialBlobSize;
            public IntPtr CredentialBlob;
            public int Persist;
            public int AttributeCount;
            public IntPtr Attributes;
            public IntPtr TargetAlias;
            public IntPtr UserName;
        }

        [DllImport("Advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CredReadW(string target, int type, int flags, out IntPtr credential);

        [DllImport("Advapi32.dll")]
        private static extern void CredFree(IntPtr buffer);

        public static string ReadGenericSecret(string target) {
            IntPtr credentialPointer;
            if (!CredReadW(target, CRED_TYPE_GENERIC, 0, out credentialPointer)) {
                throw new Win32Exception(Marshal.GetLastWin32Error(), "Credential Manager entry was not available.");
            }
            try {
                var credential = Marshal.PtrToStructure<CREDENTIAL>(credentialPointer);
                if (credential.CredentialBlob == IntPtr.Zero || credential.CredentialBlobSize == 0) {
                    throw new InvalidOperationException("Credential Manager entry has no secret.");
                }
                var bytes = new byte[credential.CredentialBlobSize];
                try {
                    Marshal.Copy(credential.CredentialBlob, bytes, 0, bytes.Length);
                    return Encoding.Unicode.GetString(bytes).TrimEnd('\0');
                }
                finally {
                    Array.Clear(bytes, 0, bytes.Length);
                }
            }
            finally {
                CredFree(credentialPointer);
            }
        }
    }
}
'@
}

function Get-ProofLoopQwenGenericSecret {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidatePattern('^[A-Za-z0-9._/-]+$')]
        [string]$Target
    )

    return [ProofLoop.QwenCredentialNative]::ReadGenericSecret($Target)
}
