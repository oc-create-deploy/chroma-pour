Shader "Custom/WaterMask"
{
    Properties
    {
        _MainTex ("Sprite Texture", 2D) = "white" {}
        _Cutoff ("Height Cutoff", Range(0,1)) = 1.0 // 控制可见部分的高度
    }
    SubShader
    {
        Tags {"Queue"="Transparent" "RenderType"="Transparent"}
        Blend SrcAlpha OneMinusSrcAlpha
        Cull Off
        ZWrite Off
        
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            struct appdata_t {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f {
                float2 uv : TEXCOORD0;
                float4 vertex : SV_POSITION;
            };

            sampler2D _MainTex;
            float _Cutoff; // 控制显示的水位高度

            v2f vert (appdata_t v)
            {
                v2f o;
                o.vertex = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            fixed4 frag (v2f i) : SV_Target
            {
                fixed4 col = tex2D(_MainTex, i.uv);

                // 只渲染小于 Cutoff 高度的部分
                if (i.uv.y > _Cutoff)
                    discard;

                return col;
            }
            ENDCG
        }
    }
}
